#!/usr/bin/env python3
"""
=============================================================================
onvif_server.py — Lightweight ONVIF Device Discovery Server
=============================================================================
Simulates ONVIF-compatible IP cameras so NVRs can auto-discover them.
Each camera gets a unique ONVIF device service on a different port.

Implements:
  - WS-Discovery (UDP multicast port 3702) for auto-discovery
  - Basic ONVIF Device Service (GetCapabilities, GetDeviceInformation)
  - GetProfiles / GetStreamUri returning RTSP URLs

Usage:
  python3 onvif_server.py --cameras 10 --host 192.168.1.100 --rtsp-port 8554

NVR auto-discovery will find cameras as:
  http://192.168.1.100:10001/onvif/device_service  (camera 1)
  http://192.168.1.100:10002/onvif/device_service  (camera 2)
  ...
=============================================================================
"""

import argparse
import socket
import struct
import threading
import uuid
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
import time
import sys
import logging

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("onvif-sim")

# WS-Discovery multicast group
WSD_MCAST_ADDR = "239.255.255.250"
WSD_PORT = 3702
ONVIF_BASE_PORT = 10001  # Camera 1 = port 10001, Camera 2 = 10002, etc.

# ─── WS-Discovery Responder ──────────────────────────────────────────────────

PROBE_RESPONSE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope
  xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope"
  xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
  xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery"
  xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <SOAP-ENV:Header>
    <wsa:MessageID>urn:uuid:{msg_uuid}</wsa:MessageID>
    <wsa:RelatesTo>{relates_to}</wsa:RelatesTo>
    <wsa:To>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:To>
    <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/ProbeMatches</wsa:Action>
  </SOAP-ENV:Header>
  <SOAP-ENV:Body>
    <wsd:ProbeMatches>
      <wsd:ProbeMatch>
        <wsa:EndpointReference>
          <wsa:Address>urn:uuid:{device_uuid}</wsa:Address>
        </wsa:EndpointReference>
        <wsd:Types>dn:NetworkVideoTransmitter</wsd:Types>
        <wsd:Scopes>
          onvif://www.onvif.org/type/video_encoder
          onvif://www.onvif.org/hardware/SimCamera
          onvif://www.onvif.org/name/SimCam-{cam_num}
          onvif://www.onvif.org/location/NetworkCamera
        </wsd:Scopes>
        <wsd:XAddrs>http://{host}:{port}/onvif/device_service</wsd:XAddrs>
        <wsd:MetadataVersion>1</wsd:MetadataVersion>
      </wsd:ProbeMatch>
    </wsd:ProbeMatches>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""


def wsd_listener(cameras, host):
    """Listen for WS-Discovery Probe messages and respond for each camera."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(("", WSD_PORT))

    mreq = struct.pack("4sL", socket.inet_aton(WSD_MCAST_ADDR), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    log.info(f"WS-Discovery listener on UDP {WSD_PORT}")
    print(f"[ONVIF] WS-Discovery listening on UDP {WSD_PORT} (multicast)")

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            msg = data.decode("utf-8", errors="ignore")

            if "Probe" in msg and "NetworkVideoTransmitter" in msg:
                # Extract MessageID for RelatesTo
                try:
                    root = ET.fromstring(msg)
                    ns = {"wsa": "http://schemas.xmlsoap.org/ws/2004/08/addressing"}
                    relates = root.find(".//wsa:MessageID", ns)
                    relates_to = relates.text if relates is not None else "urn:uuid:unknown"
                except Exception:
                    relates_to = "urn:uuid:unknown"

                # Send one ProbeMatch per camera (with small delay to avoid flooding)
                for cam in cameras:
                    response = PROBE_RESPONSE_TEMPLATE.format(
                        msg_uuid=str(uuid.uuid4()),
                        relates_to=relates_to,
                        device_uuid=cam["uuid"],
                        cam_num=cam["num"],
                        host=host,
                        port=cam["port"]
                    )
                    time.sleep(0.05)
                    sock.sendto(response.encode(), addr)

        except Exception as e:
            log.debug(f"WSD error: {e}")


# ─── ONVIF HTTP Device Service ───────────────────────────────────────────────

def make_onvif_handler(cam_info):
    """Factory: creates an HTTP handler bound to a specific camera."""

    class ONVIFHandler(BaseHTTPRequestHandler):
        cam = cam_info

        def log_message(self, fmt, *args):
            pass  # Suppress default HTTP logging

        def do_GET(self):
            if self.path in ("/", "/onvif/device_service"):
                self.send_response(200)
                self.send_header("Content-Type", "text/xml")
                self.end_headers()
                self.wfile.write(self._wsdl().encode())
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8", errors="ignore")
            response = self._dispatch(body)
            self.send_response(200)
            self.send_header("Content-Type", "application/soap+xml; charset=utf-8")
            self.end_headers()
            self.wfile.write(response.encode())

        def _dispatch(self, body):
            if "GetSystemDateAndTime" in body:
                return self._soap(self._date_time_response())
            elif "GetCapabilities" in body:
                return self._soap(self._capabilities_response())
            elif "GetDeviceInformation" in body:
                return self._soap(self._device_info_response())
            elif "GetProfiles" in body:
                return self._soap(self._profiles_response())
            elif "GetStreamUri" in body:
                return self._soap(self._stream_uri_response())
            elif "GetVideoEncoderConfigurations" in body:
                return self._soap(self._encoder_config_response())
            else:
                return self._soap("<tds:GetCapabilitiesResponse/>")

        def _soap(self, body):
            return f"""<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope
  xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope"
  xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
  xmlns:tt="http://www.onvif.org/ver10/schema"
  xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
  xmlns:trt2="http://www.onvif.org/ver20/media/wsdl">
  <SOAP-ENV:Body>{body}</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

        def _date_time_response(self):
            now = datetime.utcnow()
            return f"""<tds:GetSystemDateAndTimeResponse>
  <tds:SystemDateAndTime>
    <tt:DateTimeType>NTP</tt:DateTimeType>
    <tt:DaylightSavings>false</tt:DaylightSavings>
    <tt:TimeZone><tt:TZ>UTC</tt:TZ></tt:TimeZone>
    <tt:UTCDateTime>
      <tt:Time><tt:Hour>{now.hour}</tt:Hour><tt:Minute>{now.minute}</tt:Minute><tt:Second>{now.second}</tt:Second></tt:Time>
      <tt:Date><tt:Year>{now.year}</tt:Year><tt:Month>{now.month}</tt:Month><tt:Day>{now.day}</tt:Day></tt:Date>
    </tt:UTCDateTime>
  </tds:SystemDateAndTime>
</tds:GetSystemDateAndTimeResponse>"""

        def _capabilities_response(self):
            h = self.cam['host']
            p = self.cam['port']
            return f"""<tds:GetCapabilitiesResponse>
  <tds:Capabilities>
    <tt:Media>
      <tt:XAddr>http://{h}:{p}/onvif/media_service</tt:XAddr>
      <tt:StreamingCapabilities>
        <tt:RTPMulticast>false</tt:RTPMulticast>
        <tt:RTP_TCP>true</tt:RTP_TCP>
        <tt:RTP_RTSP_TCP>true</tt:RTP_RTSP_TCP>
      </tt:StreamingCapabilities>
    </tt:Media>
    <tt:Device>
      <tt:XAddr>http://{h}:{p}/onvif/device_service</tt:XAddr>
    </tt:Device>
  </tds:Capabilities>
</tds:GetCapabilitiesResponse>"""

        def _device_info_response(self):
            n = self.cam['num']
            return f"""<tds:GetDeviceInformationResponse>
  <tds:Manufacturer>SimCam</tds:Manufacturer>
  <tds:Model>VirtualCamera-{n:03d}</tds:Model>
  <tds:FirmwareVersion>1.0.0</tds:FirmwareVersion>
  <tds:SerialNumber>SIM{n:06d}</tds:SerialNumber>
  <tds:HardwareId>SIMCAM-HW-1.0</tds:HardwareId>
</tds:GetDeviceInformationResponse>"""

        def _profiles_response(self):
            n = self.cam['num']
            return f"""<trt:GetProfilesResponse>
  <trt:Profiles token="Profile_1" fixed="true">
    <tt:Name>MainStream</tt:Name>
    <tt:VideoSourceConfiguration token="VideoSource_1">
      <tt:Name>VideoSource_1</tt:Name>
      <tt:UseCount>1</tt:UseCount>
      <tt:SourceToken>VideoSource_1</tt:SourceToken>
      <tt:Bounds x="0" y="0" width="1920" height="1080"/>
    </tt:VideoSourceConfiguration>
    <tt:VideoEncoderConfiguration token="VideoEncoder_1">
      <tt:Name>VideoEncoder_1</tt:Name>
      <tt:UseCount>1</tt:UseCount>
      <tt:Encoding>H264</tt:Encoding>
      <tt:Resolution><tt:Width>1920</tt:Width><tt:Height>1080</tt:Height></tt:Resolution>
      <tt:Quality>5</tt:Quality>
      <tt:RateControl>
        <tt:FrameRateLimit>25</tt:FrameRateLimit>
        <tt:EncodingInterval>1</tt:EncodingInterval>
        <tt:BitrateLimit>4096</tt:BitrateLimit>
      </tt:RateControl>
      <tt:H264>
        <tt:GovLength>50</tt:GovLength>
        <tt:H264Profile>High</tt:H264Profile>
      </tt:H264>
    </tt:VideoEncoderConfiguration>
  </trt:Profiles>
</trt:GetProfilesResponse>"""

        def _stream_uri_response(self):
            h = self.cam['host']
            p = self.cam['rtsp_port']
            n = self.cam['num']
            return f"""<trt:GetStreamUriResponse>
  <trt:MediaUri>
    <tt:Uri>rtsp://{h}:{p}/cam{n}</tt:Uri>
    <tt:InvalidAfterConnect>false</tt:InvalidAfterConnect>
    <tt:InvalidAfterReboot>false</tt:InvalidAfterReboot>
    <tt:Timeout>PT60S</tt:Timeout>
  </trt:MediaUri>
</trt:GetStreamUriResponse>"""

        def _encoder_config_response(self):
            return """<trt:GetVideoEncoderConfigurationsResponse>
  <trt:Configurations token="VideoEncoder_1">
    <tt:Name>VideoEncoder_1</tt:Name>
    <tt:Encoding>H264</tt:Encoding>
    <tt:Resolution><tt:Width>1920</tt:Width><tt:Height>1080</tt:Height></tt:Resolution>
    <tt:Quality>5</tt:Quality>
  </trt:Configurations>
</trt:GetVideoEncoderConfigurationsResponse>"""

        def _wsdl(self):
            return """<?xml version="1.0"?><definitions xmlns="http://schemas.xmlsoap.org/wsdl/"><service name="DeviceService"/></definitions>"""

    return ONVIFHandler


def start_camera_server(cam_info):
    handler = make_onvif_handler(cam_info)
    server = HTTPServer(("0.0.0.0", cam_info["port"]), handler)
    print(f"[ONVIF] Camera {cam_info['num']:>3d} → http://{cam_info['host']}:{cam_info['port']}/onvif/device_service  (RTSP: /cam{cam_info['num']})")
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="ONVIF Camera Simulator")
    parser.add_argument("--cameras",   type=int, default=10,    help="Number of cameras")
    parser.add_argument("--host",      type=str, default="",    help="Host IP (auto-detect if blank)")
    parser.add_argument("--rtsp-port", type=int, default=8554,  help="RTSP port (MediaMTX)")
    parser.add_argument("--base-port", type=int, default=10001, help="First ONVIF HTTP port")
    args = parser.parse_args()

    # Auto-detect host IP
    if not args.host:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            args.host = s.getsockname()[0]
            s.close()
        except Exception:
            args.host = "127.0.0.1"

    print(f"\n{'='*60}")
    print(f"  ONVIF Camera Simulator")
    print(f"  Cameras   : {args.cameras}")
    print(f"  Host IP   : {args.host}")
    print(f"  RTSP Port : {args.rtsp_port}")
    print(f"  ONVIF ports: {args.base_port} – {args.base_port + args.cameras - 1}")
    print(f"{'='*60}\n")

    cameras = []
    for i in range(1, args.cameras + 1):
        cameras.append({
            "num":       i,
            "uuid":      str(uuid.uuid5(uuid.NAMESPACE_DNS, f"simcam-{i}")),
            "host":      args.host,
            "port":      args.base_port + i - 1,
            "rtsp_port": args.rtsp_port,
        })

    # Start WS-Discovery listener
    wsd_thread = threading.Thread(target=wsd_listener, args=(cameras, args.host), daemon=True)
    try:
        wsd_thread.start()
    except Exception as e:
        print(f"[WARN] WS-Discovery failed (needs root / port 3702): {e}")

    # Start ONVIF HTTP server per camera (threaded)
    threads = []
    for cam in cameras:
        t = threading.Thread(target=start_camera_server, args=(cam,), daemon=True)
        t.start()
        threads.append(t)

    print(f"\n[ONVIF] All {args.cameras} cameras ready for NVR discovery.\n")
    print(f"        In Exacq: Add Camera → ONVIF → scan {args.host}")
    print(f"        Or manually: http://{args.host}:{args.base_port}/onvif/device_service\n")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n[ONVIF] Shutting down.")
        sys.exit(0)


if __name__ == "__main__":
    main()
