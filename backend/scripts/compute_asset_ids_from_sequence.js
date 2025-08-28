#!/usr/bin/env node
const { createUmi } = require('@metaplex-foundation/umi-bundle-defaults');
const { mplBubblegum, findLeafAssetIdPda } = require('@metaplex-foundation/mpl-bubblegum');
const { publicKey } = require('@metaplex-foundation/umi');

// Ordered by mint time in migration logs
const txs = [
  { token_id: '105', sig: '5U2DPKGpfdShn9rHgUsTk69XCUeq9WqcjYLViEmfcpp8S5pxRy4YyNtuup2NFbubvk9NqC634fq5g1g5XKdLb7jp' },
  { token_id: '106', sig: '3ds8roYVoaXJH9XCaEQEQii3kRvnMA5e2BHopLXNVuU9yHRhVSuQWWKJpQgtzvUkfgDtA6YC8k1rtbgf1xMCpt83' },
  { token_id: '101', sig: '2jpSLSqNqyAsBWJKz1fV4La43jgqij9iLukfk7Ugx91EbL4rHSG4EeTk1Zx3TEgHduYsbMzFKFb74nVoCEqwEXCh' },
  { token_id: '102', sig: '3auvqB7pztFsYwn7Jp11mUybCzuJviw8nEjoBNyS2Vfq8EPo59EXonJtFTxqc4dpakrK55SsQzq4uuatJrHhyq2M' },
  { token_id: '100', sig: '4u9t9xsmd2tN2E8T735wto1E2NUXBK859hyoLtzuMwByr1esr6y6gHWSie3aXrCX9Wu71eBuVp85YyPNUHM8QqUW' },
  { token_id: '107', sig: '28cJVVNbkxzum9zYdk3KfKs8ZSkiBmZvhQ4yEZpDDuYWGCS7wLC3wA82Lk2JQow4ZrH3GxYhHiQZ9EFko1y1GMT4' },
  { token_id: '103', sig: '3iBKuH1KnKviA2Q5WLdWax8YrFkp1aERmMPitBXmzSB5ukiXwcC8Vs75BJ6SiNR3a8Hnob9Xcy6WRsJxUQ98KwXY' },
  { token_id: '104', sig: '2oiyW8gvZ3z54hrnNY4ZpCm9p2rtWhPt9REsdqU4SYB3C1Y7MKZHo6KQDvqmT1c3Y48pESzUbGaUrwjMZdSVxsPE' },
  { token_id: '1', sig: '4SyCQ6Woa1tMPinWzkXJ3vcoVM2GFNVMm7mbfQpH4GoKVKm7iB7bbnnH7qQAJc2LF1YVNEeMKgTSFvricZPc4o3x' },
  { token_id: '10', sig: '31T8uPEwa5Wdsdjxj2yh69gRXaTgh7JaY5HesSPZ4xcgsYrTJeraTs9bekuSTLC8DEjFv5pRACkgrMXBAuDCrAVR' },
];

(async () => {
  const rpcUrl = process.env.SOLANA_RPC_URL || 'https://api.devnet.solana.com';
  const treeAddress = process.env.SOLANA_TREE_ADDRESS || 'erY15sCGJmk3H7y9BLZRLmmLgY8P4We1nGUsgBL5kJM';
  const umi = createUmi(rpcUrl);
  umi.use(mplBubblegum());
  const merkleTree = publicKey(treeAddress);

  const results = txs.map((t, idx) => {
    const pda = findLeafAssetIdPda(umi, { merkleTree, leafIndex: idx });
    const assetId = pda[0].toString ? pda[0].toString() : String(pda[0]);
    return { token_id: t.token_id, transaction_signature: t.sig, leaf_index: idx, asset_id: assetId, tree_address: treeAddress };
  });
  console.log(JSON.stringify({ status: 'success', results }, null, 2));
})();

