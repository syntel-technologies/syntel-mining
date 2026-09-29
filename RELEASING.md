# Releasing

Publishing is automated. A tag is the only trigger, and there is **no PyPI API token anywhere**: not in a secret,
not on a laptop. PyPI verifies the release workflow's OIDC identity on each run (Trusted Publishing), so there is
nothing to rotate and nothing to leak.

## One-time: register the trusted publisher

PyPI has to be told once which workflow may publish this project. Until then the `publish` job fails with
`invalid-publisher: valid token, but no corresponding publisher`. That is the token exchange working and being
correctly refused.

Because the project does not exist on PyPI yet, register it as a **pending publisher** at
<https://pypi.org/manage/account/publishing/>:

| Field | Value |
|---|---|
| PyPI Project Name | `syntel-mining` |
| Owner | `syntel-technologies` |
| Repository name | `syntel-mining` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

The environment name is not optional. `release.yml` runs the publish job in an environment called `pypi`, and PyPI
matches on that claim; leaving the field blank fails the exchange in exactly the same way.

After the first successful publish, the pending publisher becomes a normal one attached to the project.

## Optional: require a human before each publish

GitHub → Settings → Environments → `pypi` → **Required reviewers**. The publish job then waits, and the approval is
recorded against the release.

## Every release

1. Bump `version` in `pyproject.toml` **and** `__version__` in `src/syntel_mining/__init__.py`, and add the release to
   `CHANGELOG.md`. The workflow refuses to publish unless the tag and both versions agree.
2. Merge to `main`.
3. Tag and push:

```bash
git tag -a v0.2.0 -m "syntel-mining 0.2.0" && git push origin v0.2.0
```

The workflow then verifies the version, runs CI on Python 3.13 and 3.14, builds, checks that the metadata renders on
PyPI, publishes with attestations, and writes a GitHub release with the artefacts attached.

## If a release fails

A version number is spent only by a **successful** upload: PyPI never accepts the same version twice, even after a
deletion. A run that fails before publishing costs nothing; fix the cause and re-run the failed job, or delete the tag
and start again. A run that fails *after* uploading needs a new version number.
