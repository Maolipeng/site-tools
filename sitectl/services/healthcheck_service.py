from __future__ import annotations

import socket
import urllib.error
import urllib.request

from sitectl.models import HealthcheckProbe, HealthcheckReport, SiteRecord


class HealthcheckService:
    def tcp_probe(self, host: str, port: int, timeout: float) -> HealthcheckProbe:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            ok = sock.connect_ex((host, port)) == 0
        detail = f"tcp://{host}:{port} reachable" if ok else f"tcp://{host}:{port} unreachable"
        return HealthcheckProbe(name="local_tcp", ok=ok, detail=detail)

    def http_probe(self, name: str, url: str, timeout: float) -> HealthcheckProbe:
        request = urllib.request.Request(url, headers={"User-Agent": "sitectl/0.1.0"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", None) or response.getcode()
                ok = 200 <= status < 400
                return HealthcheckProbe(name=name, ok=ok, detail=f"{url} returned {status}", status_code=status)
        except urllib.error.HTTPError as exc:
            return HealthcheckProbe(name=name, ok=False, detail=f"{url} returned {exc.code}", status_code=exc.code)
        except urllib.error.URLError as exc:
            return HealthcheckProbe(name=name, ok=False, detail=f"{url} failed: {exc.reason}")

    def run(
        self,
        *,
        record: SiteRecord,
        path: str,
        timeout: float,
        skip_local: bool,
        skip_remote: bool,
        remote_url: str | None,
    ) -> HealthcheckReport:
        probes: list[HealthcheckProbe] = []
        normalized_path = path if path.startswith("/") else f"/{path}"

        if not skip_local and record.port:
            probes.append(self.tcp_probe("127.0.0.1", record.port, timeout))
            probes.append(
                self.http_probe(
                    "local_http",
                    f"http://127.0.0.1:{record.port}{normalized_path}",
                    timeout,
                )
            )
        elif not skip_local:
            probes.append(HealthcheckProbe(name="local", ok=True, detail="site type has no local port; local probe skipped"))

        if not skip_remote:
            target_url = remote_url or f"https://{record.domain}{normalized_path}"
            probes.append(self.http_probe("remote_https", target_url, timeout))

        return HealthcheckReport(domain=record.domain, type=record.type.value, probes=probes)
