"""
ios.py — iOS transport via pymobiledevice3

Requirements:
  pip install pymobiledevice3
  iOS 16 and below: pair via  pymobiledevice3 pair
  iOS 17+:          run       sudo python3 -m pymobiledevice3 remote tunneld
                    then pair via  pymobiledevice3 pair -t

Device must have Developer Mode enabled:
  Settings → Privacy & Security → Developer Mode → ON  (iOS 16+)
"""

try:
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.simulate_location import DtSimulateLocation
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


class IOSTransport:
    def __init__(self):
        self._lockdown = None
        self._service  = None

    def available(self) -> bool:
        return _AVAILABLE

    def connect(self) -> bool:
        if not _AVAILABLE:
            return False
        try:
            self._lockdown = create_using_usbmux()
            self._service  = DtSimulateLocation(lockdown=self._lockdown)
            return True
        except Exception:
            self._lockdown = None
            self._service  = None
            return False

    def send_location(self, lat: float, lon: float, **_) -> bool:
        if not self._service:
            return False
        try:
            self._service.set(lat, lon)
            return True
        except Exception:
            return False

    def disconnect(self):
        if self._service:
            try:
                self._service.clear()
            except Exception:
                pass
        self._lockdown = None
        self._service  = None
