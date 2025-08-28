#!/usr/bin/env node
const fs = require('fs');
const { createUmi } = require('@metaplex-foundation/umi-bundle-defaults');
const { createSignerFromKeypair, publicKey, keypairIdentity } = require('@metaplex-foundation/umi');
const { mplBubblegum, mintV1, findTreeConfigPda, parseLeafFromMintV1Transaction, findLeafAssetIdPda } = require('@metaplex-foundation/mpl-bubblegum');
const bs58 = require('bs58');

(async () => {
  try {
    const keypairPath = process.env.SOLANA_KEYPAIR || process.env.FUNDED_WALLET_PATH;
    const treeAddress = process.env.SOLANA_TREE_ADDRESS;
    const rpcUrl = process.env.SOLANA_RPC_URL || 'https://api.devnet.solana.com';
    const metaJson = process.env.MINT_METADATA_JSON;
    const metaPath = process.env.MINT_METADATA_PATH;

    if (!keypairPath || !treeAddress || (!metaJson && !metaPath)) {
      console.error(JSON.stringify({ status: 'error', error: 'Missing env: SOLANA_KEYPAIR, SOLANA_TREE_ADDRESS, and either MINT_METADATA_JSON or MINT_METADATA_PATH' }));
      process.exit(1);
    }

    let meta;
    try {
      if (metaPath) {
        meta = JSON.parse(fs.readFileSync(metaPath, 'utf8'));
      } else if (metaJson && metaJson.trim().startsWith('{')) {
        meta = JSON.parse(metaJson);
      } else {
        throw new Error('Invalid metadata input');
      }
    } catch (err) {
      console.error(JSON.stringify({ status: 'error', error: `Failed to parse metadata: ${err.message}` }));
      process.exit(1);
    }

    const kpBytes = JSON.parse(fs.readFileSync(keypairPath, 'utf8'));
    const umi = createUmi(rpcUrl);
    umi.use(mplBubblegum());
    const keypair = umi.eddsa.createKeypairFromSecretKey(Uint8Array.from(kpBytes));
    const signer = createSignerFromKeypair(umi, keypair);
    umi.use(keypairIdentity(signer));

    const merkleTree = publicKey(treeAddress);
    const treeConfig = findTreeConfigPda(umi, { merkleTree });

    const name = typeof meta?.name === 'string' ? meta.name.slice(0, 32) : '';
    const symbol = typeof meta?.symbol === 'string' ? meta.symbol.slice(0, 10) : '';
    const uri = typeof meta?.uri === 'string' ? meta.uri.slice(0, 200) : (typeof meta?.image === 'string' ? meta.image.slice(0, 200) : '');

    if (!uri) {
      throw new Error('Metadata URI is required (meta.uri or meta.image)');
    }

    const builder = await mintV1(umi, {
      leafOwner: signer.publicKey,
      merkleTree,
      treeConfig,
      metadata: {
        name,
        symbol,
        uri,
        sellerFeeBasisPoints: 0,
        primarySaleHappened: false,
        isMutable: true,
        editionNonce: null,
        tokenStandard: null,
        collection: null,
        uses: null,
        creators: [],
      },
    });

    const { signature } = await builder.sendAndConfirm(umi, { send: { commitment: 'finalized' } });
    const sig58 = typeof signature === 'string' ? signature : bs58.encode(Uint8Array.from(signature));

    // Try to parse leaf to get leafIndex and derive asset ID (cNFT mint address)
    let leafIndex = null;
    let assetId = null;
    try {
      // Retry parsing the leaf a few times to handle RPC inner-instruction availability
      for (let attempt = 0; attempt < 10 && assetId === null; attempt++) {
        try {
          const leaf = await parseLeafFromMintV1Transaction(umi, sig58);
          if (leaf && (leaf.leafIndex !== undefined)) {
            leafIndex = Number(leaf.leafIndex);
            const pda = findLeafAssetIdPda(umi, { merkleTree, leafIndex });
            assetId = pda[0].toString ? pda[0].toString() : String(pda[0]);
            break;
          }
        } catch (_) {
          // ignore and retry
        }
        await new Promise((r) => setTimeout(r, 1000));
      }
    } catch (e) {
      // Non-fatal
    }

    const out = {
      status: 'success',
      tree_address: treeAddress,
      leaf_owner: signer.publicKey.toString(),
      metadata_uri: uri,
      transaction_signature: sig58,
      asset_id: assetId,
      leaf_index: leafIndex,
      explorer_url: `https://explorer.solana.com/tx/${sig58}?cluster=devnet`,
    };

    // Print result JSON line for the Python caller to capture
    console.log(JSON.stringify(out));
  } catch (e) {
    console.error(JSON.stringify({ status: 'error', error: String(e && e.message ? e.message : e) }));
    process.exit(1);
  }
})();

