#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { createUmi } = require('@metaplex-foundation/umi-bundle-defaults');
const { generateSigner, createSignerFromKeypair, keypairIdentity } = require('@metaplex-foundation/umi');
const { mplBubblegum, createTree, findTreeConfigPda } = require('@metaplex-foundation/mpl-bubblegum');
const bs58 = require('bs58');

(async () => {
  try {
    const keypairPath = process.env.SOLANA_KEYPAIR || process.env.FUNDED_WALLET_PATH;
    if (!keypairPath) {
      console.error(JSON.stringify({ status: 'error', error: 'SOLANA_KEYPAIR not set' }));
      process.exit(1);
    }

    const rpcUrl = process.env.SOLANA_RPC_URL || 'https://api.devnet.solana.com';

    const kpBytes = JSON.parse(fs.readFileSync(keypairPath, 'utf8'));
    const umi = createUmi(rpcUrl);
    umi.use(mplBubblegum());
    const keypair = umi.eddsa.createKeypairFromSecretKey(Uint8Array.from(kpBytes));
    const signer = createSignerFromKeypair(umi, keypair);
    umi.use(keypairIdentity(signer));

    // Generate the Merkle tree signer (account)
    const merkleTree = generateSigner(umi);

    const treeConfig = findTreeConfigPda(umi, { merkleTree: merkleTree.publicKey });

    const maxDepth = parseInt(process.env.MAX_DEPTH || '14', 10);
    const maxBufferSize = parseInt(process.env.MAX_BUFFER_SIZE || '64', 10);
    const isPublic = (process.env.PUBLIC || 'true') === 'true';

    const builder = await createTree(umi, {
      merkleTree,
      treeConfig,
      maxDepth,
      maxBufferSize,
      public: isPublic,
    });

    const { signature } = await builder.sendAndConfirm(umi, { send: { commitment: 'finalized' } });

    // Normalize signature to base58 string
    let sig58;
    if (typeof signature === 'string') {
      sig58 = signature;
    } else if (signature && signature.length !== undefined) {
      sig58 = bs58.encode(Uint8Array.from(signature));
    } else {
      sig58 = String(signature);
    }

    const out = {
      status: 'success',
      tree_address: merkleTree.publicKey.toString(),
      tree_config: treeConfig[0].toString ? treeConfig[0].toString() : String(treeConfig[0]),
      max_depth: maxDepth,
      max_buffer_size: maxBufferSize,
      public: isPublic,
      transaction_signature: sig58,
      explorer_url: `https://explorer.solana.com/tx/${sig58}?cluster=devnet`,
    };
    console.log(JSON.stringify(out));
  } catch (e) {
    console.error(JSON.stringify({ status: 'error', error: String(e && e.message ? e.message : e) }));
    process.exit(1);
  }
})();

