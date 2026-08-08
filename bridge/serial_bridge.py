"""
Serial <-> /api/v1/ingest bridge process. Runs as a separate process so a wedged serial port
can't take the FastAPI backend down with it.
Owner: Asad (protocol specifics agreed with Irfan — see docs/team-briefs/IRFAN.md).
"""
