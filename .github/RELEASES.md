# Automated releases

Shader Alchemist publishes GitHub Releases from semantic-version tags.

## Publish a release

1. Make sure the changes intended for the release are merged into `main`.
2. Create and push a version tag:

   ```bash
   git checkout main
   git pull --ff-only
   git tag -a v0.1.0 -m "Shader Alchemist v0.1.0"
   git push origin v0.1.0
   ```

3. GitHub Actions runs `.github/workflows/release.yml`, creates a GitHub Release, and generates release notes from merged pull requests and commits.

Use semantic versioning:
- `v0.1.0` for an initial public preview
- `v0.2.0` for backward-compatible feature additions
- `v0.2.1` for backward-compatible fixes
- `v1.0.0` when the project is ready to declare its initial stable API

Prerelease tags such as `v0.2.0-rc.1` are accepted. The workflow publishes a GitHub Release and does not build or upload binaries; add artifact build/upload steps when the project has stable distributable artifacts.

To run manually, open **Actions → Automated Release → Run workflow** and enter an existing version tag. Existing releases are not overwritten.
