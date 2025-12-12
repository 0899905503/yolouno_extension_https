import usocket
import ure

# ============================================================
# SAFE CALLBACK EXECUTION
# ============================================================
def _run_callback(cb):
    try:
        result = cb()
        # async?
        if hasattr(result, "__await__") or hasattr(result, "__next__"):
            try:
                next(result)
            except StopIteration:
                pass
    except Exception as e:
        print("Callback error:", e)


# ============================================================
# HTTP RESPONSE OBJECT
# ============================================================
class Response:

    def __init__(self, f):
        self.raw = f
        self.encoding = "utf-8"
        self._cached = None
        self.status_code = None
        self.reason = None
        self.headers = None
        self.cookies = None
        self.url = None

    def close(self):
        if self.raw:
            self.raw.close()
            self.raw = None
        self._cached = None

    def is_successed(self):
        return self.status_code in (200, 201, 202, 204, 302)

    def on_successed(self, cb):
        if self.status_code in (200, 201, 202, 204, 302):
            _run_callback(cb)
        return self

    def on_failed(self, cb):
        if self.status_code not in (200, 201, 202, 204, 302):
            _run_callback(cb)
        return self

    @property
    def content(self):
        if self._cached is None:
            try:
                self._cached = self.raw.read()
            finally:
                self.raw.close()
                self.raw = None
        return self._cached

    @property
    def text(self):
        return str(self.content, self.encoding)

    def json(self):
        import ujson
        return ujson.loads(self.content)


# ============================================================
# LOW LEVEL HTTP REQUEST
# ============================================================
def request(method, url, params=None, cookies=None, data=None, json=None,
            headers={}, parse_headers=True, followRedirect=True):

    while True:
        try:
            proto, dummy, host, path = url.split("/", 3)
        except ValueError:
            proto, dummy, host = url.split("/", 2)
            path = ""

        if proto == "http:":
            port = 80
        elif proto == "https:":
            try:
                import ussl
            except:
                import ssl as ussl
            port = 443
        else:
            raise ValueError("Unsupported protocol: " + proto)

        if ":" in host:
            host, port = host.split(":", 1)
            port = int(port)

        ai = usocket.getaddrinfo(host, port, 0, usocket.SOCK_STREAM)[0]

        resp_d = {} if parse_headers else None

        s = usocket.socket(ai[0], ai[1], ai[2])
        s.settimeout(60.0)

        try:
            s.connect(ai[-1])
            if proto == "https:":
                import ussl
                s = ussl.wrap_socket(s, server_hostname=host)

            # ---- SEND REQUEST ----
            s.write(b"%s /%s HTTP/1.0\r\n" % (method, path))

            if "Host" not in headers:
                s.write(b"Host: %s\r\n" % host)

            for k in headers:
                s.write(k)
                s.write(b": ")
                s.write(headers[k])
                s.write(b"\r\n")

            if cookies:
                for ck in cookies:
                    s.write(b"Cookie: ")
                    s.write(ck)
                    s.write(b"=")
                    s.write(cookies[ck])
                    s.write(b"\r\n")

            if json is not None:
                import ujson
                data = ujson.dumps(json)
                s.write(b"Content-Type: application/json\r\n")

            if data:
                s.write(b"Content-Length: %d\r\n" % len(data))

            s.write(b"Connection: close\r\n\r\n")

            if data:
                s.write(data)

            # =====================================================
            # READ FIRST LINE OF HEADER
            # Google Script sometimes sends malformed HTTP headers
            # => FIX: if fail → assume success (200)
            # =====================================================
            l = s.readline()

            try:
                parts = l.split(None, 2)
                status = int(parts[1])
                reason = parts[2].rstrip() if len(parts) > 2 else b""
            except:
                status = 200
                reason = b"OK"

            # READ ALL HEADERS
            while True:
                l = s.readline()
                if not l or l == b"\r\n":
                    break
                if not parse_headers:
                    continue

                try:
                    k, v = l.decode().split(":", 1)
                    resp_d[k.strip()] = v.strip()
                except:
                    pass

        except OSError:
            s.close()
            raise

        break

    resp = Response(s)
    resp.url = url
    resp.status_code = status
    resp.reason = reason
    resp.headers = resp_d
    resp.cookies = cookies

    return resp


# ============================================================
# SHORTCUTS
# ============================================================
def head(url, **kw):  return request("HEAD",  url, **kw)
def get(url, **kw):   return request("GET",   url, **kw)
def post(url, **kw):  return request("POST",  url, **kw)
def put(url, **kw):   return request("PUT",   url, **kw)
def patch(url, **kw): return request("PATCH", url, **kw)
def delete(url, **kw):return request("DELETE",url, **kw)
