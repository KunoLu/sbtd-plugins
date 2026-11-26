// One finite R1 identity, independently reviewed in
// reviewy-r1-two-skills-review-20261121.md §§2–3/5. No candidate-generated trust.
// Frozen inputs: cloud-r1-two-skills-20261121-2133 new-output-identities.json
// (f0af24f87b3f0cf3dd15c00c3a3a4bc087e55ac3ede22fc85af31046eda15c11),
// new-full-asset-source-license-map.json
// (733edccf5970233c126de0d938b6df317f551eff532b5874950ac933a8aa92b0),
// and the sealed ledger/manifest cross-checked against after-output-vector.json.
// The complete ledger binds all four MIT repositories, sixteen trees, the three
// selected / eight unchanged Matt owners, and the nested domain component input.
// Raw/root seals additionally bind exact notice bytes and every closed asset.
export const reviewedR1ReleaseProfile = {
  repository: "mattpocock-skills-r1-manuals",
  rootSha256:
    "871756771756195451b3c2343e05a3cdf5c04c0d8033a1352f59584b03212e63",
  rawLedgerSha256:
    "4eed938088d7415f2dbcac7a2a576baa9cbbc179184fca484493f54ef60e13ad",
  semanticLedgerSha256:
    "b4cc88099e80ac0a7f20909d30fc2cbfaa8deaeef1ca4fd443ef1aef7c08f3d4",
  canonical: {
    sourceId: "sbtd-workflow-kit-upstream",
    canonicalSourceUri: "https://github.com/KunoLu/640-skills",
    resolvedRevision: "1d82494d74f6df9bca7dccef2da409f87091883e",
    sourceTreeSha256:
      "c1fc3f679c375a22c6272de92c3377ac04ea8edb996acd314ea76f73257739b0",
    transformVersion: "p0-v4",
    manifestSha256:
      "97c71dddf82415b936ae07314e8057183a1a8d0e17e32b02cbc6626fc6f49404",
    generatedSha256:
      "de3686e03a49ae2abe9c677f3b520136fc75ab0c6c32adb2ae871ab217b9c2a2",
  },
  projection: {
    policyVersion: 1,
    policySha256:
      "1dfe7f19f6118b4303484163cca691589dd79dac3d33ebe11ce04dec2d331a6f",
    decisionsSha256:
      "bbed74b7f811f728585c7c03b30abc3172e9b37382a405a0e8806344275f5146",
    counts: {
      included: 261,
      omitted: 81,
      replaced: 10,
    },
  },
  overlays: {
    "AGENTS.global.md":
      "dc69bc818bc2eefc20fe00e50afc571adef164b8340f67741e10070ff75a3e3c",
    "AGENTS.project-root.md":
      "06784deffc181524fe555cc110be69fa8047494ebf926a60dc68340f00c71631",
    "onboard/runtime/catalog.json":
      "7f3bb2adff0d9f5fc5509b79190036fa34227ec2a987a01421ce327245f95e73",
    "onboard/runtime/catalog.schema.json":
      "f787490acf0209c8d09d260a0dd2c9ed3d20842d956ccab1a3095e0599c5489a",
    "onboard/runtime/templates/project/gitignore.template":
      "4972b0fbb303c99a05f060b3a43c3860c8b88ff4ad9d32a9b1b27e07eb9fb2b9",
    "onboard/runtime/templates/skills/gherkin-bdd/SKILL.md":
      "e5cf2a13a5a1b04d82bff09781f75cfef1663685e61093316e0eb6b4a1598435",
    "onboard/runtime/templates/skills/sbtd-task/references/presentation.md":
      "3a9be511b307210f9ed3a4d5f793a9ed07854652871e05deac07bdab745cf7f5",
    "onboard/runtime/templates/skills/seo-geo/references/schema-templates.md":
      "25a876cbce2ab441e5f66eeac7b3d745fc6730c94287220bf6659ea0f8b1bbb4",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/README.md":
      "58fc8fffbef881b0769b8fe2e9dbe5dc3919951b320e7459fd6278b38b3cbb8b",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/README.zh-CN.md":
      "7f5e1aff2090739fdd358787e2ec68ddb5240d2f330a859fb62ee65f9d2cea7b",
  },
  ledger: {
    schemaVersion: 1,
    stableSet: "2026-09-14.6",
    promotedAt: "2026-09-14",
    sourceSelection: {
      kind: "mixed-source",
      scope: "r1-manuals",
      base: {
        canonicalRevision: "1d82494d74f6df9bca7dccef2da409f87091883e",
        canonicalManifestSha256:
          "97c71dddf82415b936ae07314e8057183a1a8d0e17e32b02cbc6626fc6f49404",
        policySha256:
          "1dfe7f19f6118b4303484163cca691589dd79dac3d33ebe11ce04dec2d331a6f",
        stableSet: "2026-09-14.6",
        promotedAt: "2026-09-14",
      },
      inputPath: "omp-source-selections/r1-manuals/selection.json",
      inputSha256:
        "290bdc6379f3f55376ac24ac660598c3013408f376834d6d96ca92b739cd90c4",
      domain: {
        role: "validated-component-input",
        receipt: {
          kind: "mixed-source",
          scope: "domain-modeling-only",
          base: {
            canonicalRevision: "1d82494d74f6df9bca7dccef2da409f87091883e",
            canonicalManifestSha256:
              "97c71dddf82415b936ae07314e8057183a1a8d0e17e32b02cbc6626fc6f49404",
            policySha256:
              "1dfe7f19f6118b4303484163cca691589dd79dac3d33ebe11ce04dec2d331a6f",
            stableSet: "2026-09-14.6",
            promotedAt: "2026-09-14",
          },
          inputPath: "omp-source-selections/domain-modeling/selection.json",
          inputSha256:
            "6cb1e695b18e76aa771be1ab052085878763a96197205bc4a0f5874384814684",
          record: {
            schemaVersion: 1,
            scope: "domain-modeling-only",
            owner: "third-party",
            supplier: {
              repository: "https://github.com/KunoLu/640-skills",
              revision: "3c835303c23d59d3157ca84121a92f1bd87d4997",
              path: "sbtd-workflow-onboard/assets/external-skills/stable/skills/domain-modeling",
            },
            origin: {
              repository: "https://github.com/mattpocock/skills.git",
              sourceSubpath: "skills/engineering/domain-modeling",
              license: "MIT",
            },
            base: {
              canonicalRevision: "1d82494d74f6df9bca7dccef2da409f87091883e",
              canonicalManifestSha256:
                "97c71dddf82415b936ae07314e8057183a1a8d0e17e32b02cbc6626fc6f49404",
              policySha256:
                "1dfe7f19f6118b4303484163cca691589dd79dac3d33ebe11ce04dec2d331a6f",
              repositoryKey: "mattpocock-skills",
              repositoryRevision: "3cca18b368ae95cdbdebbff572ccafa662551015",
              treeSha256:
                "731ecd11825453ec3d813ac26e7a082bb458bc332781c6dba18d7004468139d7",
              absent: ["GLOSSARY-FORMAT.md"],
            },
            target: {
              repositoryKey: "mattpocock-skills-domain-modeling",
              repositoryRevision: "4ae2317ddb22b046e26455e4f9c9b3aaaf62212d",
              treeSha256:
                "c0bd13ce078a3c8eb5507fc9067165dad89b10f11b33b26e29a5c62f9c840bd2",
              absent: ["CONTEXT-FORMAT.md"],
            },
            license: {
              blob: "f1dd2c09108dde1a5f56097cee8461b3ea834499",
              mode: "100644",
              sha256:
                "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5",
              bytes: 1068,
              path: "licenses/mattpocock-skills-LICENSE",
            },
            files: [
              {
                path: "ADR-FORMAT.md",
                operation: "keep",
                before: {
                  blob: "d7e61f30a9fd8ca70d9ee68f019c2a9ebf2d13f7",
                  mode: "100644",
                  sha256:
                    "944c92aa790e8fbdc9199640b170979abb8a34ba8d0fe18c2a01a63bce140ca0",
                  bytes: 2733,
                },
                target: {
                  blob: "d7e61f30a9fd8ca70d9ee68f019c2a9ebf2d13f7",
                  mode: "100644",
                  sha256:
                    "944c92aa790e8fbdc9199640b170979abb8a34ba8d0fe18c2a01a63bce140ca0",
                  bytes: 2733,
                },
              },
              {
                path: "CONTEXT-FORMAT.md",
                operation: "delete",
                before: {
                  blob: "79bbb32f6fda55758b377c980f72a6cb2b8c670e",
                  mode: "100644",
                  sha256:
                    "17ab16ce783e4d2801ee52fd9acdf550cbf44de65ae76797a93943bbedf22a13",
                  bytes: 2290,
                },
                target: null,
              },
              {
                path: "GLOSSARY-FORMAT.md",
                operation: "add",
                before: null,
                target: {
                  blob: "9c0b4c7a2e8507c23cbb5e0baa66d81699321cc6",
                  mode: "100644",
                  sha256:
                    "21dcc40cdec8e151a829b98ab1517c1867bc444e3665134a98c6983411996801",
                  bytes: 2300,
                },
              },
              {
                path: "SKILL.md",
                operation: "replace",
                before: {
                  blob: "9b97707e19ef1f590aada356f2b3f6bb881f91be",
                  mode: "100644",
                  sha256:
                    "327a2b50620e2fd70abc6893cd6965e76b20f8d0adb0dc2c8d5eb3845efb643e",
                  bytes: 3331,
                },
                target: {
                  blob: "a4438c6879c517d1a08e2b5fbca049b632688dfe",
                  mode: "100644",
                  sha256:
                    "7b925d7b1e341a2eeae33ad68a8a8c0ab889a38ddd22a7598e4c240e5a7556a3",
                  bytes: 3346,
                },
              },
              {
                path: "agents/openai.yaml",
                operation: "keep",
                before: {
                  blob: "7f1522d2f11506ee205275ab7c282aa52366ecf6",
                  mode: "100644",
                  sha256:
                    "f6bf2aa996c6e6f53fdd0708e18a0d16a56aed8322cca59fedbe3c0d2c75f06b",
                  bytes: 101,
                },
                target: {
                  blob: "7f1522d2f11506ee205275ab7c282aa52366ecf6",
                  mode: "100644",
                  sha256:
                    "f6bf2aa996c6e6f53fdd0708e18a0d16a56aed8322cca59fedbe3c0d2c75f06b",
                  bytes: 101,
                },
              },
            ],
          },
        },
      },
      record: {
        schemaVersion: 1,
        scope: "r1-manuals",
        owner: "third-party",
        supplier: {
          repository: "https://github.com/KunoLu/640-skills",
          revision: "3c835303c23d59d3157ca84121a92f1bd87d4997",
          path: "sbtd-workflow-onboard/assets/external-skills/stable",
        },
        origin: {
          repository: "https://github.com/mattpocock/skills.git",
          license: "MIT",
        },
        base: {
          canonicalRevision: "1d82494d74f6df9bca7dccef2da409f87091883e",
          canonicalManifestSha256:
            "97c71dddf82415b936ae07314e8057183a1a8d0e17e32b02cbc6626fc6f49404",
          policySha256:
            "1dfe7f19f6118b4303484163cca691589dd79dac3d33ebe11ce04dec2d331a6f",
          repositoryKey: "mattpocock-skills",
          repositoryRevision: "3cca18b368ae95cdbdebbff572ccafa662551015",
        },
        target: {
          repositoryKey: "mattpocock-skills-r1-manuals",
          repositoryRevision: "4ae2317ddb22b046e26455e4f9c9b3aaaf62212d",
        },
        domainSelection: {
          inputPath: "omp-source-selections/domain-modeling/selection.json",
          inputSha256:
            "6cb1e695b18e76aa771be1ab052085878763a96197205bc4a0f5874384814684",
        },
        license: {
          blob: "f1dd2c09108dde1a5f56097cee8461b3ea834499",
          mode: "100644",
          sha256:
            "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5",
          bytes: 1068,
          path: "licenses/mattpocock-skills-LICENSE",
        },
        skills: [
          {
            name: "grilling",
            sourceSubpath: "skills/productivity/grilling",
            beforeTreeSha256:
              "b0af4cb93507011cab704853dc540ae142dec2a1256d374a38f4f196a04f7b50",
            targetTreeSha256:
              "3a7559839f45dfa4491f045d56647148c2b90f0e5ce0b5355301ef0e6d1bc428",
            files: [
              {
                path: "SKILL.md",
                operation: "replace",
                before: {
                  blob: "8ca78c6d8f901aab0c5a1f896034b70e666ff2a3",
                  mode: "100644",
                  sha256:
                    "10ff989e7498b23b5acb49d5048f11dcd906757d2f79c5cdf8a00001381296f2",
                  bytes: 1987,
                },
                target: {
                  blob: "d2f09a18e6a6c65c55f1271ba08dfeaf06f0bed3",
                  mode: "100644",
                  sha256:
                    "a146842ed93ca43d833550fa9adf02e58cb63c83fea9d4b4522995b82242d4e2",
                  bytes: 2077,
                },
              },
              {
                path: "agents/openai.yaml",
                operation: "keep",
                before: {
                  blob: "ddbdb96139c0c1dfe6bca698f39d0465674b8a39",
                  mode: "100644",
                  sha256:
                    "1411d7df7d99b7e621a1ff8283c8133cc2464be63d064e52d8ce169c6800ee9b",
                  bytes: 113,
                },
                target: {
                  blob: "ddbdb96139c0c1dfe6bca698f39d0465674b8a39",
                  mode: "100644",
                  sha256:
                    "1411d7df7d99b7e621a1ff8283c8133cc2464be63d064e52d8ce169c6800ee9b",
                  bytes: 113,
                },
              },
            ],
          },
          {
            name: "to-tickets",
            sourceSubpath: "skills/engineering/to-tickets",
            beforeTreeSha256:
              "7d82d3f4b50f4f57bafc8e361cdf6b06fde6f3b940bbd13199a184e98f0d34c4",
            targetTreeSha256:
              "98422855972ffb35bf33ce3eee1c1255f58e81cf801d6d3fc0185bb8e0351839",
            files: [
              {
                path: "SKILL.md",
                operation: "replace",
                before: {
                  blob: "e868c831fcfb1e124e010bcdf84a429ec879160f",
                  mode: "100644",
                  sha256:
                    "5c9fba69845c2519b9b35b9af42ae5142c21f8ca15ac2123dc2722002c8058ae",
                  bytes: 5671,
                },
                target: {
                  blob: "9b77a01db9460c99c22d03c910c349f890f12c0e",
                  mode: "100644",
                  sha256:
                    "56ec23c5b2782785d4e65bff9e315b6d3aeb4ef977c174a219e99489fada1995",
                  bytes: 5812,
                },
              },
              {
                path: "agents/openai.yaml",
                operation: "keep",
                before: {
                  blob: "24605a5db64e4fc750b999aa94aea126bee814ee",
                  mode: "100644",
                  sha256:
                    "21bc6215fffcd7614e9f772bb1760e87cc5fc7dcc707e7d282bc9414267a6090",
                  bytes: 146,
                },
                target: {
                  blob: "24605a5db64e4fc750b999aa94aea126bee814ee",
                  mode: "100644",
                  sha256:
                    "21bc6215fffcd7614e9f772bb1760e87cc5fc7dcc707e7d282bc9414267a6090",
                  bytes: 146,
                },
              },
            ],
          },
        ],
        presentation: {
          path: "onboard/runtime/templates/skills/sbtd-task/references/presentation.md",
          supplierPath:
            "sbtd-workflow-onboard/templates/skills/sbtd-task/references/presentation.md",
          owner: "kpi",
          license: "Apache-2.0",
          operation: "replace",
          target: {
            blob: "b4e12e1775c98915b816a69a082557d466166245",
            mode: "100644",
            sha256:
              "3a9be511b307210f9ed3a4d5f793a9ed07854652871e05deac07bdab745cf7f5",
            bytes: 6271,
          },
        },
      },
      sourceOperations: [
        {
          path: "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/CONTEXT-FORMAT.md",
          operation: "delete",
          source: "domain-modeling",
          targetSha256: null,
        },
        {
          path: "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/GLOSSARY-FORMAT.md",
          operation: "add",
          source: "domain-modeling",
          targetSha256:
            "21dcc40cdec8e151a829b98ab1517c1867bc444e3665134a98c6983411996801",
        },
        {
          path: "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/SKILL.md",
          operation: "replace",
          source: "domain-modeling",
          targetSha256:
            "7b925d7b1e341a2eeae33ad68a8a8c0ab889a38ddd22a7598e4c240e5a7556a3",
        },
        {
          path: "onboard/runtime/assets/external-skills/stable/skills/grilling/SKILL.md",
          operation: "replace",
          source: "r1-manuals",
          targetSha256:
            "a146842ed93ca43d833550fa9adf02e58cb63c83fea9d4b4522995b82242d4e2",
        },
        {
          path: "onboard/runtime/assets/external-skills/stable/skills/to-tickets/SKILL.md",
          operation: "replace",
          source: "r1-manuals",
          targetSha256:
            "56ec23c5b2782785d4e65bff9e315b6d3aeb4ef977c174a219e99489fada1995",
        },
        {
          path: "onboard/runtime/templates/skills/sbtd-task/references/presentation.md",
          operation: "replace",
          source: "omp-overlay",
          targetSha256:
            "3a9be511b307210f9ed3a4d5f793a9ed07854652871e05deac07bdab745cf7f5",
        },
      ],
      finalOwnership: {
        "diagnosing-bugs": "mattpocock-skills",
        tdd: "mattpocock-skills",
        "grill-me": "mattpocock-skills",
        "grill-with-docs": "mattpocock-skills",
        grilling: "mattpocock-skills-r1-manuals",
        "domain-modeling": "mattpocock-skills-r1-manuals",
        "codebase-design": "mattpocock-skills",
        handoff: "mattpocock-skills",
        "writing-for-agents": "mattpocock-skills",
        "to-spec": "mattpocock-skills",
        "to-tickets": "mattpocock-skills-r1-manuals",
      },
    },
    repositories: {
      "mattpocock-skills": {
        url: "https://github.com/mattpocock/skills.git",
        revision: "3cca18b368ae95cdbdebbff572ccafa662551015",
        license: "MIT",
        licenseFiles: [
          {
            source: "LICENSE",
            stablePath: "licenses/mattpocock-skills-LICENSE",
          },
        ],
      },
      "ui-ux-pro-max-skill": {
        url: "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.git",
        revision: "7f69fed6a2717900085f1bc3b263721f8ba025e2",
        license: "MIT",
        licenseFiles: [
          {
            source: "LICENSE",
            stablePath: "licenses/ui-ux-pro-max-skill-LICENSE",
          },
        ],
      },
      ponytail: {
        url: "https://github.com/DietrichGebert/ponytail.git",
        revision: "356918eba965ee1eac64bd3a7f0dd02108350de5",
        license: "MIT",
        licenseFiles: [
          {
            source: "LICENSE",
            stablePath: "licenses/ponytail-LICENSE",
          },
        ],
      },
      "mattpocock-skills-r1-manuals": {
        url: "https://github.com/mattpocock/skills.git",
        revision: "4ae2317ddb22b046e26455e4f9c9b3aaaf62212d",
        license: "MIT",
        licenseFiles: [
          {
            source: "LICENSE",
            stablePath: "licenses/mattpocock-skills-LICENSE",
          },
        ],
      },
    },
    skills: {
      "diagnosing-bugs": {
        repository: "mattpocock-skills",
        sourceSubpath: "skills/engineering/diagnosing-bugs",
        stablePath: "skills/diagnosing-bugs",
        treeSha256:
          "8b7b1621013eb3ab3c689e477321b372bf411037c46fa417987d05e3e28f0416",
      },
      tdd: {
        repository: "mattpocock-skills",
        sourceSubpath: "skills/engineering/tdd",
        stablePath: "skills/tdd",
        treeSha256:
          "eef2fe20ae9372fea0a6bb083c65582e6c41089e0897e28274c49f05ccc97dd2",
      },
      "grill-me": {
        repository: "mattpocock-skills",
        sourceSubpath: "skills/productivity/grill-me",
        stablePath: "skills/grill-me",
        treeSha256:
          "1d7b1f48eb68647a94058d75d80902c351adb013a93bdb98c1218fffb2896bc3",
      },
      "grill-with-docs": {
        repository: "mattpocock-skills",
        sourceSubpath: "skills/engineering/grill-with-docs",
        stablePath: "skills/grill-with-docs",
        treeSha256:
          "04ba6a6139df57e6a011eb79311212fa5f3dc47ec6177845d1defea19c68bb60",
      },
      grilling: {
        repository: "mattpocock-skills-r1-manuals",
        sourceSubpath: "skills/productivity/grilling",
        stablePath: "skills/grilling",
        treeSha256:
          "3a7559839f45dfa4491f045d56647148c2b90f0e5ce0b5355301ef0e6d1bc428",
      },
      "domain-modeling": {
        repository: "mattpocock-skills-r1-manuals",
        sourceSubpath: "skills/engineering/domain-modeling",
        stablePath: "skills/domain-modeling",
        treeSha256:
          "c0bd13ce078a3c8eb5507fc9067165dad89b10f11b33b26e29a5c62f9c840bd2",
      },
      "codebase-design": {
        repository: "mattpocock-skills",
        sourceSubpath: "skills/engineering/codebase-design",
        stablePath: "skills/codebase-design",
        treeSha256:
          "7767d3c4ca04b8ce94ec28d25ca4632eeac39be9df0ff5bfbfbe1dbb7a3cabdb",
      },
      handoff: {
        repository: "mattpocock-skills",
        sourceSubpath: "skills/productivity/handoff",
        stablePath: "skills/handoff",
        treeSha256:
          "c8646a846de8896217189af07caee05204df6aa15601dcf4a4edb791043f20e2",
      },
      "writing-for-agents": {
        repository: "mattpocock-skills",
        sourceSubpath: "skills/productivity/writing-for-agents",
        stablePath: "skills/writing-for-agents",
        treeSha256:
          "4ea87a30fea2e91ac4a24fb3f0aa2a2ba3bc5273634fb573cfdb254781f34713",
      },
      "to-spec": {
        repository: "mattpocock-skills",
        sourceSubpath: "skills/engineering/to-spec",
        stablePath: "skills/to-spec",
        treeSha256:
          "b913e4b0bdffff43ea38fc6874d238663039eb8ab73755fc300a541df877d1a9",
      },
      "to-tickets": {
        repository: "mattpocock-skills-r1-manuals",
        sourceSubpath: "skills/engineering/to-tickets",
        stablePath: "skills/to-tickets",
        treeSha256:
          "98422855972ffb35bf33ce3eee1c1255f58e81cf801d6d3fc0185bb8e0351839",
      },
      "ui-ux-pro-max": {
        repository: "ui-ux-pro-max-skill",
        sourceSubpath: ".claude/skills/ui-ux-pro-max",
        stablePath: "skills/ui-ux-pro-max",
        treeSha256:
          "93f67a282405730a1e225e8dc3c772950c25eef3e467e3d2fc2eb42da6165486",
      },
      ponytail: {
        repository: "ponytail",
        sourceSubpath: "skills/ponytail",
        stablePath: "skills/ponytail",
        treeSha256:
          "1f70d9e01f5e924aa2328546e32c349df1842ff9ed0979445a31000151c6e5c5",
      },
      "ponytail-review": {
        repository: "ponytail",
        sourceSubpath: "skills/ponytail-review",
        stablePath: "skills/ponytail-review",
        treeSha256:
          "ff27a5ed24b6b4cf3959eb98fdba17e936861e76e81d1d3054dec3ed804d25b9",
      },
      "ponytail-audit": {
        repository: "ponytail",
        sourceSubpath: "skills/ponytail-audit",
        stablePath: "skills/ponytail-audit",
        treeSha256:
          "def4ae9e8598c66d63fa197d01771c923033da085eb26939333464d61da17ace",
      },
      "ponytail-debt": {
        repository: "ponytail",
        sourceSubpath: "skills/ponytail-debt",
        stablePath: "skills/ponytail-debt",
        treeSha256:
          "f9926b4440b0ce1c92008a0a2baff465bd4fdfacf3cbaf7652fe575dacc5345c",
      },
    },
  },
  assetLicenses: {
    "AGENTS.global.md": "Apache-2.0",
    "AGENTS.project-omp.md": "Apache-2.0",
    "AGENTS.project-root.md": "Apache-2.0",
    "catalog.json": "Apache-2.0",
    LICENSE: "Apache-2.0",
    "onboard/runtime/assets/external-skills/stable/licenses/mattpocock-skills-LICENSE":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/licenses/ponytail-LICENSE":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/licenses/ui-ux-pro-max-skill-LICENSE":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/MANIFEST.json": "Apache-2.0",
    "onboard/runtime/assets/external-skills/stable/skills/codebase-design/agents/openai.yaml":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/codebase-design/DEEPENING.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/codebase-design/DESIGN-IT-TWICE.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/codebase-design/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/diagnosing-bugs/agents/openai.yaml":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/diagnosing-bugs/scripts/hitl-loop.template.sh":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/diagnosing-bugs/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/ADR-FORMAT.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/agents/openai.yaml":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/GLOSSARY-FORMAT.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/grill-me/agents/openai.yaml":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/grill-me/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/grill-with-docs/agents/openai.yaml":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/grill-with-docs/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/grilling/agents/openai.yaml":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/grilling/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/handoff/agents/openai.yaml":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/handoff/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ponytail-audit/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ponytail-debt/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ponytail-review/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ponytail/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/tdd/agents/openai.yaml":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/tdd/mocking.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/tdd/SKILL.md": "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/tdd/tests.md": "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/to-spec/agents/openai.yaml":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/to-spec/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/to-tickets/agents/openai.yaml":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/to-tickets/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/app-interface.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/catalog-summary.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/charts.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/colors.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/data-provenance.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/google-font-licenses.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/google-fonts.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/icons.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/landing.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/motion.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/phosphor-icons-upstream.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/products.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/react-performance.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/angular.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/astro.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/avalonia.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/flutter.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/html-tailwind.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/javafx.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/jetpack-compose.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/laravel.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/nextjs.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/nuxt-ui.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/nuxtjs.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/react-native.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/react.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/shadcn.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/svelte.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/swiftui.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/threejs.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/uno.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/uwp.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/vue.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/winui.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/wpf.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/styles.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/typography.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/ui-reasoning.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/ux-guidelines.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/references/pro-rules.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/references/quick-reference.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/core.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/design_system.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/reasoning_contract.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/search.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-api.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-catalog.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-existing.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-metadata.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-overrides.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/icons-curated.csv":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-core.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-package.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-react-exports.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-react-package.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/relevance-baseline.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/relevance-cases.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/relevance-thresholds.json":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_catalog_refresh.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_catalog_summary_line_endings.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_core_data_quality.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_core.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_data_contracts.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_design_system_mode.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_design_system_stack.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_native_desktop_stack_freshness.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_relevance_evaluator.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_skill_script_paths.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_style_taxonomy.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_text_layout_resilience.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_web_stack_freshness.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/validate_data.py":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/writing-for-agents/agents/openai.yaml":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/writing-for-agents/SKILL-MECHANICS.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/skills/writing-for-agents/SKILL.md":
      "MIT",
    "onboard/runtime/assets/external-skills/stable/THIRD_PARTY_NOTICES.md":
      "Apache-2.0",
    "onboard/runtime/assets/graft-build-policy.json": "Apache-2.0",
    "onboard/runtime/assets/graft-hook-entry.mjs": "Apache-2.0",
    "onboard/runtime/assets/graft-instructions.txt": "Apache-2.0",
    "onboard/runtime/assets/migration-legacy-ownership.json": "Apache-2.0",
    "onboard/runtime/assets/migration-local-ignore.txt": "Apache-2.0",
    "onboard/runtime/assets/migration-paused-agents.txt": "Apache-2.0",
    "onboard/runtime/assets/routing-approval.pub": "Apache-2.0",
    "onboard/runtime/assets/runtime-lineage.json": "Apache-2.0",
    "onboard/runtime/assets/runtime-lineage.pub": "Apache-2.0",
    "onboard/runtime/catalog.json": "Apache-2.0",
    "onboard/runtime/catalog.schema.json": "Apache-2.0",
    "onboard/runtime/examples/catalog.minimal.json": "Apache-2.0",
    "onboard/runtime/LICENSE": "Apache-2.0",
    "onboard/runtime/NOTICE": "Apache-2.0",
    "onboard/runtime/onboard-contracts.schema.json": "Apache-2.0",
    "onboard/runtime/requirements.txt": "Apache-2.0",
    "onboard/runtime/scripts/graft_runtime.py": "Apache-2.0",
    "onboard/runtime/scripts/onboard_arguments.py": "Apache-2.0",
    "onboard/runtime/scripts/onboard_contracts.py": "Apache-2.0",
    "onboard/runtime/scripts/onboard.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_backup_retention.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_cleanup_legacy.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_cleanup_targets.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_cleanup_upgrade.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_codex_wiring.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_graft_deployment.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_graft_entry.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_handoff.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_identity.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_migration_files.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_migration_legacy.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_migration_plan.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_migration_verify.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_migration.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_omp_sources.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_omp_wiring.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_probe_links.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_project.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_reconciliation.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_recovery.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_task_document.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_task_routing.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_task_state.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_trellis_uninstall.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_upgrade_cli.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_upgrade_hosts.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_upgrade_inventory.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_upgrade_paths.py": "Apache-2.0",
    "onboard/runtime/scripts/sbtd_upgrade.py": "Apache-2.0",
    "onboard/runtime/templates/project/gitignore.template": "Apache-2.0",
    "onboard/runtime/templates/skills/book-ddd-distilled-modeling/LICENSE":
      "Apache-2.0",
    "onboard/runtime/templates/skills/book-ddd-distilled-modeling/NOTICE":
      "Apache-2.0",
    "onboard/runtime/templates/skills/book-ddd-distilled-modeling/SKILL.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/book-ddia-data-design/LICENSE":
      "Apache-2.0",
    "onboard/runtime/templates/skills/book-ddia-data-design/NOTICE":
      "Apache-2.0",
    "onboard/runtime/templates/skills/book-ddia-data-design/SKILL.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/book-legacy-change-safety/LICENSE":
      "Apache-2.0",
    "onboard/runtime/templates/skills/book-legacy-change-safety/NOTICE":
      "Apache-2.0",
    "onboard/runtime/templates/skills/book-legacy-change-safety/SKILL.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/book-refactoring-pass/LICENSE":
      "Apache-2.0",
    "onboard/runtime/templates/skills/book-refactoring-pass/NOTICE":
      "Apache-2.0",
    "onboard/runtime/templates/skills/book-refactoring-pass/SKILL.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/book-release-readiness/LICENSE":
      "Apache-2.0",
    "onboard/runtime/templates/skills/book-release-readiness/NOTICE":
      "Apache-2.0",
    "onboard/runtime/templates/skills/book-release-readiness/SKILL.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/gherkin-bdd/LICENSE": "Apache-2.0",
    "onboard/runtime/templates/skills/gherkin-bdd/NOTICE": "Apache-2.0",
    "onboard/runtime/templates/skills/gherkin-bdd/SKILL.md": "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/LICENSE":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/NOTICE":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/references/artifact-manifest.schema.json":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/references/deployment-manifest.example.yaml":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/references/deployment-manifest.schema.json":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/references/evidence-decision.schema.json":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/references/metrics.schema.json":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/references/product.example.yaml":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/references/product.schema.json":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/references/revision-set.schema.json":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/references/runner-job.schema.json":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/references/runner-result.schema.json":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/references/runtime-contract.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/references/workspace.local.example.yaml":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/references/workspace.schema.json":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/requirements.txt":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/scripts/knowledge_base_p1.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/knowledge-base-integration/SKILL.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/lessons-record/LICENSE": "Apache-2.0",
    "onboard/runtime/templates/skills/lessons-record/NOTICE": "Apache-2.0",
    "onboard/runtime/templates/skills/lessons-record/references/identity-migration.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/lessons-record/SKILL.md": "Apache-2.0",
    "onboard/runtime/templates/skills/maestro-mobile-e2e/LICENSE": "Apache-2.0",
    "onboard/runtime/templates/skills/maestro-mobile-e2e/NOTICE": "Apache-2.0",
    "onboard/runtime/templates/skills/maestro-mobile-e2e/references/ios-real-device-setup.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/maestro-mobile-e2e/references/lessons-index.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/maestro-mobile-e2e/SKILL.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/project-validation/LICENSE": "Apache-2.0",
    "onboard/runtime/templates/skills/project-validation/NOTICE": "Apache-2.0",
    "onboard/runtime/templates/skills/project-validation/references/run-summary.zh-CN.md.template":
      "Apache-2.0",
    "onboard/runtime/templates/skills/project-validation/references/validation-evidence-contract.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/project-validation/references/validation-evidence.schema.json":
      "Apache-2.0",
    "onboard/runtime/templates/skills/project-validation/references/validation-evidence.v2.schema.json":
      "Apache-2.0",
    "onboard/runtime/templates/skills/project-validation/requirements.txt":
      "Apache-2.0",
    "onboard/runtime/templates/skills/project-validation/scripts/validate_validation_evidence.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/project-validation/SKILL.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/sbtd-task/LICENSE": "Apache-2.0",
    "onboard/runtime/templates/skills/sbtd-task/NOTICE": "Apache-2.0",
    "onboard/runtime/templates/skills/sbtd-task/references/handoff.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/sbtd-task/references/methods.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/sbtd-task/references/presentation.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/sbtd-task/references/state.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/sbtd-task/references/strict.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/sbtd-task/references/task-data.schema.json":
      "Apache-2.0",
    "onboard/runtime/templates/skills/sbtd-task/references/tooling.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/sbtd-task/SKILL.md": "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/LICENSE": "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/NOTICE": "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/references/geo-research.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/references/google-docs-summary.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/references/platform-algorithms.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/references/schema-templates.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/references/seo-checklist.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/references/tools-and-apis.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/scripts/autocomplete_ideas.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/scripts/backlinks.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/scripts/competitor_gap.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/scripts/credential.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/scripts/dataforseo_api.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/scripts/domain_overview.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/scripts/keyword_research.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/scripts/related_keywords.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/scripts/seo_audit.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/scripts/serp_analysis.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/seo-geo/SKILL.md": "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/agents/openai.yaml":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/auth-fixture.ts.template":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/github-actions-e2e.yml.template":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/package-scripts.json.template":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/page-object.ts.template":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/page-spec.ts.template":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/playwright.config.ts.template":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/summary.zh-CN.md.template":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/gitignore.template":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/LICENSE":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/NOTICE":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/README.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/README.zh-CN.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/references/coverage-rubric.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/references/output-contract.md":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/scripts/analyze_failures.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/scripts/audit_selectors.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/scripts/check_coverage.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/scripts/generate_manifest.py":
      "Apache-2.0",
    "onboard/runtime/templates/skills/web-ui-autotest-generator/SKILL.md":
      "Apache-2.0",
    "onboard/runtime/upgrade.schema.json": "Apache-2.0",
    "THIRD_PARTY_NOTICES.md": "Apache-2.0",
    "third-party/sbtd-workflow-onboard/LICENSE": "Apache-2.0",
    "third-party/sbtd-workflow-onboard/NOTICE": "Apache-2.0",
  },
} as const;
