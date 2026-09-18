# Connectome data

`example_connectome_manifest.json` is a **synthetic test fixture only**. It is not biological connectome data.

Real datasets should be converted into `fca.connectome.v1` manifests with:

- an explicit version;
- source name;
- source-file SHA-256 when available;
- bounded input-channel indices;
- stable unit IDs;
- neuron class labels;
- explicit input edges.

The importer must never relabel a synthetic fixture as biological data.
