#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { createUmi } = require('@metaplex-foundation/umi-bundle-defaults');
const { mplBubblegum, findLeafAssetIdPda } = require('@metaplex-foundation/mpl-bubblegum');
const { publicKey } = require('@metaplex-foundation/umi');

function listNftFolders(baseDir) {
  return fs.readdirSync(baseDir)
    .filter((f) => f.startsWith('nft_'))
    .map((f) => path.join(baseDir, f))
    .filter((p) => fs.existsSync(path.join(p, '05_solana_mint_result.json')));
}

(async () => {
  try {
    const outDir = process.env.OUTPUT_DIR || process.argv[2];
    if (!outDir) {
      console.error(JSON.stringify({ status: 'error', error: 'Provide OUTPUT_DIR env or as first arg (path to migration_output/<run>)' }));
      process.exit(1);
    }
    const treeAddress = process.env.SOLANA_TREE_ADDRESS;
    if (!treeAddress) {
      console.error(JSON.stringify({ status: 'error', error: 'SOLANA_TREE_ADDRESS env is required' }));
      process.exit(1);
    }
    const rpcUrl = process.env.SOLANA_RPC_URL || 'https://api.devnet.solana.com';

    const umi = createUmi(rpcUrl);
    umi.use(mplBubblegum());
    const merkleTree = publicKey(treeAddress);

    const nftFolders = listNftFolders(outDir);
    const items = [];
    for (const folder of nftFolders) {
      const p = path.join(folder, '05_solana_mint_result.json');
      try {
        const data = JSON.parse(fs.readFileSync(p, 'utf8'));
        if (data && data.status === 'success' && (!data.asset_id || !data.leaf_index)) {
          items.push({
            folder,
            file: p,
            tx: data.transaction_signature,
            ts: new Date(data.timestamp).getTime() || 0,
          });
        }
      } catch (_) {}
    }

    if (items.length === 0) {
      console.log(JSON.stringify({ status: 'noop', message: 'No files to backfill' }));
      return;
    }

    // Sort by timestamp ascending (mint order in this run)
    items.sort((a, b) => a.ts - b.ts);

    // Compute asset IDs using leaf_index by order
    const results = [];
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      const pda = findLeafAssetIdPda(umi, { merkleTree, leafIndex: i });
      const assetId = pda[0].toString ? pda[0].toString() : String(pda[0]);

      // Patch JSON file
      const obj = JSON.parse(fs.readFileSync(it.file, 'utf8'));
      obj.asset_id = assetId;
      obj.leaf_index = i;
      obj.mint_address = assetId; // store asset_id as mint address for cNFTs
      fs.writeFileSync(it.file, JSON.stringify(obj, null, 2));

      results.push({ folder: path.basename(it.folder), transaction_signature: it.tx, leaf_index: i, asset_id: assetId });
    }

    console.log(JSON.stringify({ status: 'success', count: results.length, results }, null, 2));
  } catch (e) {
    console.error(JSON.stringify({ status: 'error', error: String(e && e.message ? e.message : e) }));
    process.exit(1);
  }
})();

