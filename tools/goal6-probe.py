"""Continuously record trusted HTTPS samples. SIGTERM requests a clean stop."""
import csv
import datetime
import json
import signal
import ssl
import sys
import time
import urllib.request

stopping = False


def stop(signum, frame):
    global stopping
    stopping = True


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
context = ssl.create_default_context()
with open(sys.argv[1], 'w', newline='') as output:
    writer = csv.writer(output)
    writer.writerow(['utc', 'status', 'node', 'version', 'latency_ms', 'error'])
    output.flush()
    while not stopping:
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        start = time.monotonic()
        status, node, version, error = 0, '', '', ''
        try:
            with urllib.request.urlopen(
                'https://portal.opsdemo.test/health', context=context, timeout=5
            ) as response:
                status = response.status
                data = json.load(response)
                node, version = data.get('node', ''), data.get('version', '')
        except Exception as exc:
            status = getattr(exc, 'code', 0)
            error = type(exc).__name__
        writer.writerow([timestamp, status, node, version,
                         round(1000 * (time.monotonic() - start), 1), error])
        output.flush()
        if not stopping:
            time.sleep(1)
