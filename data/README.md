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

## FlyWire Codex static exports

FCA can now build `fca.connectome.v1` manifests directly from local FlyWire Codex `.csv` or `.csv.gz` exports with `flywire_codex_files_to_manifest()`.

The importer is intentionally offline and streaming:

- FCA does not download or mirror FlyWire data;
- the caller chooses an annotation column and exact pre/post labels;
- only selected root IDs are joined against the connection table;
- synapse counts are summed per directed pair across rows/neuropils before thresholding;
- selected IDs, candidate pairs and output units have explicit hard limits;
- both input files are SHA-256 hashed and bound into the manifest source provenance.

Use official static exports obtained under the applicable FlyWire/Codex terms. Do not commit large raw connectome exports to this repository.
