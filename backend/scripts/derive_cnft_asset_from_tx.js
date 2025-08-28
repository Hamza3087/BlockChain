#!/usr/bin/env node
const { createUmi } = require('@metaplex-foundation/umi-bundle-defaults');
const { mplBubblegum, parseLeafFromMintV1Transaction, findLeafAssetIdPda } = require('@metaplex-foundation/mpl-bubblegum');
const { publicKey } = require('@metaplex-foundation/umi');

(async () => {
  try {
    const rpcUrl = process.env.SOLANA_RPC_URL || 'https://api.devnet.solana.com';
    const treeAddress = process.env.SOLANA_TREE_ADDRESS;
    const txSig = process.env.SOLANA_TX_SIGNATURE;
    if (!treeAddress || !txSig) {
      console.error(JSON.stringify({ status: 'error', error: 'Missing env: SOLANA_TREE_ADDRESS and SOLANA_TX_SIGNATURE' }));
      process.exit(1);
    }
    const umi = createUmi(rpcUrl);
    umi.use(mplBubblegum());

    const leaf = await parseLeafFromMintV1Transaction(umi, txSig);
    const leafIndex = Number(leaf.leafIndex);
    const merkleTree = publicKey(treeAddress);
    const pda = findLeafAssetIdPda(umi, { merkleTree, leafIndex });

    const out = {
      status: 'success',
      tree_address: treeAddress,
      transaction_signature: txSig,
      leaf_index: leafIndex,
      asset_id: pda[0].toString ? pda[0].toString() : String(pda[0]),
    };
    console.log(JSON.stringify(out));
  } catch (e) {
    console.error(JSON.stringify({ status: 'error', error: String(e && e.message ? e.message : e) }));
    process.exit(1);
  }
})();

