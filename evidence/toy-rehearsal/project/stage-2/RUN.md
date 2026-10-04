# Shared counter

From this directory, build and start with:

```sh
docker build -t toy-stage-2 . && docker run --rm -p 8080:8080 -e PORT=8080 toy-stage-2
```

For a custom port, replace both `8080` values in the port mapping and the
`PORT` value, for example `-p 9000:9000 -e PORT=9000`.
The service binds all interfaces, defaults to port 8080, and needs no runtime
downloads. Its single process shares one memory-only counter across clients;
restarting it resets the value to zero. No external services are required.

Read `GET /health` or `GET /counter`, increment with
`POST /counter/increment` (empty body or `{}`), and synchronously reset with
`POST /_test/reset` and an integer JSON value such as `{"value":7}`.

Run the focused host HTTP checks with Python 3.12:

```sh
python -m unittest discover -s . -p 'test_*.py' -v
```

Open http://localhost:8080/ to view the counter and add 1. Reload to see
changes from other browsers. If an update cannot be confirmed, reload to
read the authoritative value before trying again. All page assets are local.
