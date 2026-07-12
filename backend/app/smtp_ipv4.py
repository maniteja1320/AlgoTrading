"""SMTP helpers that connect over IPv4 (avoids broken IPv6 routes on some hosts)."""
from __future__ import annotations

import logging
import socket
import ssl
import smtplib

logger = logging.getLogger(__name__)

_TLS_CONTEXT = ssl.create_default_context()


def resolve_ipv4(host: str, port: int) -> str:
    """Return the first IPv4 address for host."""
    infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    if not infos:
        raise OSError(f"No IPv4 address for {host}:{port}")
    return infos[0][4][0]


def _ipv4_socket(host: str, port: int, timeout: float | None) -> socket.socket:
    last_err: OSError | None = None
    for _family, _type, _proto, _canon, sockaddr in socket.getaddrinfo(
        host, port, socket.AF_INET, socket.SOCK_STREAM
    ):
        sock = socket.socket(_family, _type, _proto)
        try:
            if timeout is not None:
                sock.settimeout(timeout)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            last_err = exc
            sock.close()
    raise last_err or OSError(f"Cannot connect to {host}:{port} via IPv4")


class IPv4SMTP(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        ip = resolve_ipv4(host, port)
        logger.info("SMTP IPv4 connect %s (%s):%s STARTTLS", host, ip, port)
        return _ipv4_socket(host, port, timeout)


class IPv4SMTP_SSL(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        ip = resolve_ipv4(host, port)
        logger.info("SMTP IPv4 connect %s (%s):%s SSL", host, ip, port)
        sock = _ipv4_socket(host, port, timeout)
        return self.context.wrap_socket(sock, server_hostname=host)


def send_via_smtp(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    mail_from: str,
    mail_to: str,
    message: str,
    use_ssl: bool,
    timeout: float = 30,
) -> None:
    if use_ssl:
        with IPv4SMTP_SSL(host, port, timeout=timeout, context=_TLS_CONTEXT) as smtp:
            smtp.login(user, password)
            smtp.sendmail(mail_from, [mail_to], message)
        return

    with IPv4SMTP(host, port, timeout=timeout) as smtp:
        smtp.ehlo()
        smtp.starttls(context=_TLS_CONTEXT)
        smtp.ehlo()
        smtp.login(user, password)
        smtp.sendmail(mail_from, [mail_to], message)
