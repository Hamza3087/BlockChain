#!/usr/bin/env node
const fs = require('fs');
const { createUmi } = require('@metaplex-foundation/umi-bundle-defaults');
const { mplBubblegum, parseLeafFromMintV1Transaction, findLeafAssetIdPda } = require('@metaplex-foundation/mpl-bubblegum');
const { publicKey } = require('@metaplex-foundation/umi');

const transactions = [
  { token_id: '105', signature: '5U2DPKGpfdShn9rHgUsTk69XCUeq9WqcjYLViEmfcpp8S5pxRy4YyNtuup2NFbubvk9NqC634fq5g1g5XKdLb7jp' },
  { token_id: '106', signature: '3ds8roYVoaXJH9XCaEQEQii3kRvnMA5e2BHopLXNVuU9yHRhVSuQWWKJpQgtzvUkfgDtA6YC8k1rtbgf1xMCpt83' },
  { token_id: '101', signature: '2jpSLSqNqyAsBWJKz1fV4La43jgqij9iLukfk7Ugx91EbL4rHSG4EeTk1Zx3TEgHduYsbMzFKFb74nVoCEqwEXCh' },
  { token_id: '102', signature: '3auvqB7pztFsYwn7Jp11mUybCzuJviw8nEjoBNyS2Vfq8EPo59EXonJtFTxqc4dpakrK55SsQzq4uuatJrHhyq2M' },
  { token_id: '100', signature: '4u9t9xsmd2tN2E8T735wto1E2NUXBK859hyoLtzuMwByr1esr6y6gHWSie3aXrCX9Wu71eBuVp85YyPNUHM8QqUW' },
  { token_id: '107', signature: '28cJVVNbkxzum9zYdk3KfKs8ZSkiBmZvhQ4yEZpDDuYWGCS7wLC3wA82Lk2JQow4ZrH3GxYhHiQZ9EFko1y1GMT4' },
  { token_id: '103', signature: '3iBKuH1KnKviA2Q5WLdWax8YrFkp1aERmMPitBXmzSB5ukiXwcC8Vs75BJ6SiNR3a8Hnob9Xcy6WRsJxUQ98KwXY' },
  { token_id: '104', signature: '2oiyW8gvZ3z54hrnNY4ZpCm9p2rtWhPt9REsdqU4SYB3C1Y7MKZHo6KQDvqmT1c3Y48pESzUbGaUrwjMZdSVxsPE' },
  { token_id: '1', signature: '4SyCQ6Woa1tMPinWzkXJ3vcoVM2GFNVMm7mbfQpH4GoKVKm7iB7bbnnH7qQAJc2LF1YVNEeMKgTSFvricZPc4o3x' },
  { token_id: '10', signature: '31T8uPEwa5Wdsdjxj2yh69gRXaTgh7JaY5HesSPZ4xcgsYrTJeraTs9bekuSTLC8DEjFv5pRACkgrMXBAuDCrAVR' }
];

(async () => {
  try {
    const rpcUrl = process.env.SOLANA_RPC_URL || 'https://api.devnet.solana.com';
    const treeAddress = process.env.SOLANA_TREE_ADDRESS || 'erY15sCGJmk3H7y9BLZRLmmLgY8P4We1nGUsgBL5kJM';
    
    const umi = createUmi(rpcUrl);
    umi.use(mplBubblegum());
    const merkleTree = publicKey(treeAddress);

    const results = [];
    
    for (const tx of transactions) {
      try {
        const leaf = await parseLeafFromMintV1Transaction(umi, tx.signature);
        const leafIndex = Number(leaf.leafIndex);
        const pda = findLeafAssetIdPda(umi, { merkleTree, leafIndex });
        const assetId = pda[0].toString ? pda[0].toString() : String(pda[0]);
        
        results.push({
          token_id: tx.token_id,
          transaction_signature: tx.signature,
          tree_address: treeAddress,
          leaf_index: leafIndex,
          asset_id: assetId,
          status: 'success'
        });
      } catch (e) {
        results.push({
          token_id: tx.token_id,
          transaction_signature: tx.signature,
          tree_address: treeAddress,
          leaf_index: null,
          asset_id: null,
          status: 'error',
          error: String(e && e.message ? e.message : e)
        });
      }
    }

    console.log(JSON.stringify({ status: 'success', results }, null, 2));
  } catch (e) {
    console.error(JSON.stringify({ status: 'error', error: String(e && e.message ? e.message : e) }));
    process.exit(1);
  }
})();
