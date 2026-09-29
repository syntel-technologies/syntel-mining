# Security

Please report a vulnerability privately through GitHub: the repository's **Security** tab, then **Report a
vulnerability**. Please do not open a public issue for it.

We aim to acknowledge a report within three working days, and to say what we will do about it within ten.

This package parses untrusted input in one place: `syntel_mining.ocel.load` reads OCEL 2.0 JSON, refusing a log
whose references do not resolve. The miners and alignment searches take a bound (`max_states`, `max_length`) so that
an adversarial log costs bounded time and memory. A way around either is a vulnerability.
