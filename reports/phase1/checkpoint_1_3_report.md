# Checkpoint 1.3 -- Remediated Pipeline Run

<!-- PROVENANCE_START
{
  "timestamp_utc": "2026-10-08T07:55:13+00:00",
  "script": "02_clean_adjust.py",
  "script_sha256": "f78e37ed36eff57ca98b1341156ae3498b099e99be5d4c83555dd7989326f49f",
  "git_commit": "file_sha256:f78e37ed36eff57ca98b1341156ae3498b099e99be5d4c83555dd7989326f49f",
  "python_version": "3.13.16",
  "pandas_version": "3.0.5",
  "numpy_version": "2.5.3",
  "yfinance_version": "unavailable",
  "platform": "Linux-6.18.44-fc-v80-x86_64-with-glibc2.39",
  "input_files_sha256": {
    "ABB.csv": "6fec4c1f16508ff1116be389d0be16c605e635642b39bfacf979f1c4cd093adf",
    "ADANIENSOL.csv": "250f3135e01a26068fddccdb2b6bcc03a09be67c83d8c6b3fd6b215103862e08",
    "ADANIENT.csv": "691aa1032e33e13c74a2ae63561c00de126166f59145ef99f000ff7e48106a22",
    "ADANIGREEN.csv": "822cedfb06b5685ad4fbc5925fe719ba018e60a7a227d338a6486ce911f34e14",
    "ADANIPORTS.csv": "28fd2336f6a5d3262303399ba6f0fa4014e9afaf3f636c7fc09957f545ce2a0f",
    "ADANIPOWER.csv": "0572392ebe6d15d7955fa1128e6c746e5215396597c26415024e3c59141d44d2",
    "AMBUJACEM.csv": "352a24b2c96021370ce7bc6e26969ba5636b1601f3185dc474e605e2f148f9ef",
    "APOLLOHOSP.csv": "5e4980c0b8e19d6439c9e610f55bf019685da2544653009093f5e52d62262688",
    "ASIANPAINT.csv": "b6927e804ccf710def531152e3c243ed221cf855234cab5fe58c7980199e167b",
    "AXISBANK.csv": "d85672cb4a49cc8deb3de2dec0778978fa24c8f53cf8659dcc2a77d460f0a921",
    "BAJAJ-AUTO.csv": "df5426bf77ba7715cd9ae74e728caae6b450363b20efb3c323fbe8e8f4876c52",
    "BAJAJFINSV.csv": "52775c6f7dfb4b38f1a8a4b5639a9ddbfbcb0fa952ebab6da277a09ded212b1d",
    "BAJAJHLDNG.csv": "bc6952db078dcb2d80c24299725f0416baf40cb323bd742e0b35a25cdf183cd2",
    "BAJFINANCE.csv": "bf1b6fcd15aba657fffdf1d09be3c70fa2b2b0850814c44941eaecfbe7f82b7e",
    "BANKBARODA.csv": "b1dc14bb554a24161068b61b72c71d7d56b440e7382d9d00404768f7fb61ea32",
    "BEL.csv": "f1653a75f443f511ff19728714a931e2bc95d7dbf2072af00da534ca92bca3e5",
    "BHARTIARTL.csv": "7b44b162d094bbffddb64bb1cda415d4c4efda778d137a2f21c37c6c5e135ef2",
    "BOSCHLTD.csv": "25da9282eee77d2b43eebf32b7104897d029f3fbaebecb093832eb96f25cb474",
    "BPCL.csv": "89eeb652ad6407dd9ef8f25edc303e1cd881aa41d77a091d461200b7f3f097c4",
    "BRITANNIA.csv": "3cdbe7bfdbfc3388981ada18581fda098af9eb7ee468cd24382a8a7d6c8d0af9",
    "BSE.csv": "84bf12f04b7337be8dfd668348f1abde96b46b73d1520527ac830348622de378",
    "CANBK.csv": "5cd9a84d6a6b8b8029580c0e6e3914cd315cecc265e444212ff7e82d10f008e9",
    "CGPOWER.csv": "704e6bf112b1c83d4557449b443a3e2cffa0cbe2b9c6aab0b836180505bba1bd",
    "CHOLAFIN.csv": "0df6a0a987c403a6fc2f9863d238b52bf5a8672c60f5cbf88c07091eeec21e9a",
    "CIPLA.csv": "7ee996cbea3c93ceb8e7003c9026e4e4b9380f964354aefd42159f34b0f2f1c4",
    "COALINDIA.csv": "07f0e545c6d676e039f70bf1cb1bb70c07cbefe5ba97cebef9c9cff8808cc55c",
    "CUMMINSIND.csv": "f6415468722f1810302ae229f663c0c687f34e06b21cbe2185506180f11ec625",
    "DIVISLAB.csv": "292f316669b24a2fee7a06c757d94356837e9219244a16bcae5f71a305333b9d",
    "DLF.csv": "b3d3cf888da7ed0c0c18be6b878dd987481ef420075d3f9ea2429eae2d87814b",
    "DMART.csv": "a5d67aace2177ca946e5616f814ade07abba0fce3a968fa92e36dfdeca134ec0",
    "DRREDDY.csv": "a3a8c6bb35e44782aa9f0a1f96b227ee89c6bc6be66bc0e6f76a376556a9a472",
    "EICHERMOT.csv": "44ee0faa51e46097faa63c7764544b70ade0ce8234a6dc5791fa50a544f67722",
    "ENRIN.csv": "945b52247e6b31d0f49e82bd75b59763cffc0362c6d4c97fbf65c6f4caf6a1ba",
    "ETERNAL.csv": "38a128f22cb853cf8e51eb5d44c0c30d1b70a02af34afa872e0be8dc6b9c61af",
    "GAIL.csv": "31a9b497c20c77bb1bf905b7053385577c3932a06d42e42f06d5f48d97d4866c",
    "GODREJCP.csv": "b610d0f38eff9d9418d3cdd90046f6dfcde48d7321b50c0f7f0ec06a7f748b02",
    "GRASIM.csv": "e17db442402097d1fdd9f48ba019317584fd1ad863dc8c1b4921bd507606dddf",
    "HAL.csv": "6bf6e70bc24ca65279049c86cc0bbdfb5e893d29ac27ba6e25147c4b248838a2",
    "HCLTECH.csv": "faaa874b521e0aee1ac7be74e42715c1be2ce248eb9bb71a3855596cd1bf8ae8",
    "HDFCAMC.csv": "cdfaf7611b5a250bb62ff72312377cc31f7355475c4372d0e770928a25108f2d",
    "HDFCBANK.csv": "3e32cfc9469c30047431a313681b1ffa1d645588af5ed3e54f78f7a6781e550a",
    "HDFCLIFE.csv": "df42a94327e0b2fac17eabc05257bb906e0c4811783cd81a05c84c3a846a7dd2",
    "HINDALCO.csv": "649f43193fd0d4583ed2cd33f4a2ca272ed01f8c387fa2e5bafbae976e923704",
    "HINDUNILVR.csv": "f9a434c5635b3c96fd47de4ea7f216b698a36d5d7e50733c6064e180fe8b17d9",
    "HINDZINC.csv": "79336aeb50554cba7b135cea4a221901ded555c2c19e7aaf49a3f1bc8310d3df",
    "HYUNDAI.csv": "64ddd31b61bb8edd12c8b01e7dc19461dd5284f2c8e0d13bc119d6bdb7592c6e",
    "ICICIBANK.csv": "dc7897b098f2c6758a5b6b4b26663d3c9ff0056fa0eacb75ae69ae18c5043265",
    "IDEA.csv": "7499adff698b3d70e8ccdc60abf6b9a4b264a48d9d81ebaa59f54a2e44047ab9",
    "INDIAVIX.csv": "6d73e1cc0a7f0a1be1b2fb08d873f5d675b1f0dacc7ca9f3210978c4bc17bfbd",
    "INDIGO.csv": "a2d60777d670ce5f1f0c8bd21bce4dfe11555ec4fde1fb808b2ac88808c41ea3",
    "INFY.csv": "40c77c0116ee2ca6f2727d92efdad7e809ff4d11989267664ae111377bdef394",
    "IOC.csv": "9eee8fb17812f51ee5af10b78a8c1c4f1639d4864b8195b60bcb415d5515684f",
    "IRFC.csv": "cebcba7c864af96aaaeb8fa299f51c0a720a598fbcadde174078e684e4d0c978",
    "ITC.csv": "fe48fd705f7013c3e69229feee44463b220b852ad5fb35102a5bcde2522c8c6f",
    "JINDALSTEL.csv": "d38e478d35033d3337c8ad410d31854403eecad6151d57a8d6379ec95268e178",
    "JIOFIN.csv": "e96a64545f9fff513563268f37ca5ecd8810b422d0127ce6795a9dabb22893c6",
    "JSWSTEEL.csv": "7f1e2ae60cf8a4ebd22d899ba199e7ef8eb33cc15a1ac40818b81a6bce08a01a",
    "KOTAKBANK.csv": "053aeac4c97299220dea31728c6db4e77385f91550e7154a109332e0861b02cf",
    "LT.csv": "179bb12a9f133f52154ea6d87d71a7c85219c4cc79b255a5b7cf9bed6341c0fc",
    "LTM.csv": "990e66708c2fb29e590c48c9bc0890d000768fc523b5c666216f7e5b1e6212e1",
    "M&M.csv": "44d69934df39dd8db3b20ab16153a1b24fe7439470633eec120341c3bc378531",
    "MARUTI.csv": "e3e6d6b67aaf005531232b885e2e64b7f841b0609a6e7af0a8d3950500570789",
    "MAXHEALTH.csv": "6a3d025dd1bd215bcaf4f5e819217182b1ce618d082c489ce61c267d6a3d3908",
    "MAZDOCK.csv": "96af7184f7d10372a325089d5d22619bdd2d2fd696411bb8641de0ce4da5ad12",
    "MOTHERSON.csv": "80d937ce9a6dd4043890e284423fcd92e150dc4b714e6f4a6440279f8e744e4d",
    "MUTHOOTFIN.csv": "d93910f4cc9cb93139b1699c650ec92a2873b0e74d182db516763ce44f6df33e",
    "NESTLEIND.csv": "1eb6231bab47c92775ac3d62f57d70ff79171e6c007a4e9c140c590c5658d004",
    "NIFTY100.csv": "ade4f36e2403b485fe2f0b73baf069e37525ed152bc4cbabd1648a0ae38be910",
    "NIFTY50.csv": "47d11361c7032f6f6b322098fc32308f0ee00b71ad4d0d0b1dfbe5a3b6d1ed3d",
    "NTPC.csv": "7ae2b5bb3bd368d3c94ccc6006e2b4967a4d89bf390958c751d4669b9ee9a429",
    "ONGC.csv": "92cb83a3d01615c8769fecea7254fe2167eebae6e63cbcdd9bccd63d071b6219",
    "PFC.csv": "1aba7afe80bdb43792ed5878100a381ab02b72e10b7558eb3d25d5888a81de1b",
    "PIDILITIND.csv": "8af342a51398b2b3258f04aba0b41b8a5d1e858b46faf8609a81f9171e2981ef",
    "PNB.csv": "faa9cf70bb2519b744aea1cf50f349bcaba3ba2e2c485ded206852876e751e3c",
    "POLYCAB.csv": "e5322514b53cf0ed58bc011b303ede3744f695b60fdf1b10d657ad18825b55c9",
    "POWERGRID.csv": "801dd373fe6a6b0728981794ff81eefbf59f270656b1c38eab232f7d52f4c67b",
    "POWERINDIA.csv": "81f73164cf6911c53937c570f8fd8979fe69f3e7e61a8316209d1e7fc8fea4bd",
    "RELIANCE.csv": "006d420ea65934547fced67f77c5691a1758c744f3f3066209cf3e003384227d",
    "SBILIFE.csv": "9567427c0cc21976d0a99f0a88e65ef0212684af926680b5ec1eb20194de6434",
    "SBIN.csv": "8e2cc1b0f950d726901333ebd7a114ac9bc603708f3923d305e8fd2b102844c7",
    "SHRIRAMFIN.csv": "379fd044a9070c3d1ef3173ec9e503e46bba5d1a2580dd90b8068eb97702eb0f",
    "SIEMENS.csv": "3b98b2115d6f264aea4298455bf8f4b65e35aebccfd108f00c752b6ca85487e3",
    "SOLARINDS.csv": "ac967773585f331e9bf08440eb3093ab314635e8bb3aeed45318e5bcba44dc22",
    "SUNPHARMA.csv": "f1f55420e90933822f3a605e58244d6f377127ade126dfa6312c099777ca4cf0",
    "TATACAP.csv": "c72fcecd771d8ecc657b0beb0a8675839f3bd8a4217e8c3710ec8fd65905b9f5",
    "TATACONSUM.csv": "c311361356f05f7d6d1cd08dbc85c2c509963d43853cc300717f064ed8356305",
    "TATAPOWER.csv": "908e9a18da33fe1ea61badbe2163118e51e690b9bf67519eef1061c080044425",
    "TATASTEEL.csv": "bd5be17a28b4c1108b93f2c0b2f228a3e9278ada8dd55f170c73a05096bc44d4",
    "TCS.csv": "25e2985225a8d93c2e79588732ccfb910282d4d0c34ec197b19da3424f4cd11b",
    "TECHM.csv": "9176eeeeffe796c10d4ec25751641050ab04d896de2a9f0e669e1b080d782791",
    "TITAN.csv": "98244af0ed7244f262b5e5d93eebbb3e2d9ee9ede56b11707f7319dd5dc2ca1d",
    "TMCV.csv": "553f180274d0b2c6dc24f1ed1fad42edfb102685658787949462142874b33a55",
    "TMPV.csv": "aff877e0e2aa5412f79a01cb8d1834cfe145a21736f143291ab09770b4b2b6db",
    "TORNTPHARM.csv": "866df66863cf681e62833d57768c40df9851b591e51dbf8fc7a284be37bd149e",
    "TRENT.csv": "27cefede8566ac3620e044c54f556d12fce04ae99e0337a883482d655286ae10",
    "TVSMOTOR.csv": "f28e700cb852b67cfe322171e1e816e0dc68897f575c995992ec328c9533fe71",
    "ULTRACEMCO.csv": "30c3d2abffab4c71fe777399b1e570ea0b312941bcbe93a7e9fec34922ef1845",
    "UNIONBANK.csv": "a9ce75284507acd69f3c24d2d6738ababdef6a1bc52c5d728c31617f085a01cd",
    "VAML.csv": "6d10d524ab03336ce0af86992462a9d6f272554610e6b445e1d1c1653252fdad",
    "VBL.csv": "1e977d696aefe85f06f366fb53c05517d0dd2627bba39419c217509b2f74779f",
    "VEDL.csv": "13c17c8069e860b54deee41ff0c0932264e6b0cfc2ff9274f001f2ed4cf86d14",
    "WIPRO.csv": "60b19235fe1e881f70651a19f8f65753d7e3cd0c26c6f2c183dbc4343ecdc0dc",
    "ZYDUSLIFE.csv": "0134c04109cec13b7b7474649980c98fd3b5e4ea71a562a2e8ac164964413e44",
    "corp_actions.csv": "72a85e2f67a60281481bc0a2e1a1fcfea990d378e10f9f2c6e470d28d7f75b7e"
  }
}
PROVENANCE_END -->

### Provenance & Environment
- **Generated (UTC):** `2026-10-08T07:55:13+00:00`
- **Script:** `02_clean_adjust.py` (commit/hash: `file_sha256:f78e37ed36eff57ca98b1341156ae3498b099e99be5d4c83555dd7989326f49f`)
- **Environment:** Python `3.13.16`, pandas `3.0.5`, numpy `2.5.3`, yfinance `unavailable`
- **Tracked Input Files:** 104

## Run summary

- Symbols processed: 103
- Clean files written: 103
- Hard failures (exception during adjust/align): 0
- Calendar: 2910 sessions, 1 problems
- Validation: 103/103 symbols passed with zero problems
- Action-table coverage: 296 uncaught raw moves >= 15% across all symbols (no action-table entry within +/-3 sessions); 296 residual >= 15% moves remaining in the adjusted series
- Universe: 71/103 symbols flagged with an exclude_reason (survivorship/history/demerger-child)
- Elapsed: 40.7s

## Hard failures

(none)

## Known, documented limitations carried forward

- Survivorship bias: point_in_time_universe() in 02d_universe.py explicitly raises NotImplementedError -- reconstructing the historical (not current) NIFTY100 membership was out of scope for this remediation pass.
- A handful of UNVERIFIED demerger ratios in corp_actions_manual.csv do not match observed price action (see this run's validation problems for the specific symbols/dates); the detector in 02b now withholds applying them rather than fabricating a discontinuity, but the correct ratio (if any) is still unresolved for those names.

