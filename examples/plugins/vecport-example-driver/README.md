# VecPort Example Driver

This package demonstrates how a third-party driver can register itself with
VecPort through the `vecport.drivers` Python Entry Point group.

Install it from the VecPort repository for development:

```bash
python -m pip install -e examples/plugins/vecport-example-driver
```

After installation, no manual `register_driver()` call is required:

```python
from vecport import connect

db = connect("example")
```

Validate the sample implementation with the VecPort Compliance Suite:

```bash
vecport compliance --url "vecport://example"
```

This driver is an educational in-memory reference implementation, not a
production database backend. Install third-party driver plugins only from
sources you trust.
