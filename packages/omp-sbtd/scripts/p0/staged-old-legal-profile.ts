// Fixed reviewed OLD legal corpus; never generated from a candidate being admitted.
// Source: c70e417f5a35226a7a3bc72283aec656bc51270802d162d81b007e35030bf29f old fixture.
// Closed paths/third-party bytes/legal originals remain fixed. Only documented
// first-party bodies and the two bounded display fields may vary at stage.
export interface StagedLegalAsset {
  readonly license: "Apache-2.0" | "MIT";
  readonly owner: string;
  readonly sha256?: string;
}

interface StagedLegalRepository {
  readonly url: string;
  readonly revision: string;
  readonly license: "MIT";
  readonly licenseFiles: readonly {
    readonly source: "LICENSE";
    readonly stablePath: string;
  }[];
}

interface StagedLegalSkill {
  readonly repository: string;
  readonly sourceSubpath: string;
  readonly stablePath: string;
  readonly treeSha256: string;
}

export interface StagedOldLegalProfile {
  readonly canonical: {
    readonly sourceId: string;
    readonly canonicalSourceUri: string;
    readonly transformVersion: string;
  };
  readonly assets: Readonly<Record<string, StagedLegalAsset>>;
  readonly overlayPaths: readonly string[];
  readonly ledger: {
    readonly schemaVersion: 1;
    readonly repositories: Readonly<Record<string, StagedLegalRepository>>;
    readonly skills: Readonly<Record<string, StagedLegalSkill>>;
  };
  readonly topNoticeParts: {
    readonly beforeRevision: string;
    readonly betweenRevisionAndStableSet: string;
    readonly afterStableSet: string;
  };
  readonly stableNotice: string;
  readonly projection: {
    readonly policyVersion: number;
    readonly counts: {
      readonly included: number;
      readonly omitted: number;
      readonly replaced: number;
    };
  };
}

let cachedProfile: StagedOldLegalProfile | undefined;

export function getStagedOldLegalProfile(): StagedOldLegalProfile {
  if (cachedProfile !== undefined) return cachedProfile;
  cachedProfile = {
    canonical: {
      sourceId: "sbtd-workflow-kit-upstream",
      canonicalSourceUri: "https://github.com/KunoLu/640-skills",
      transformVersion: "p0-v4",
    },
    assets: {
      "AGENTS.global.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "AGENTS.project-omp.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "AGENTS.project-root.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "catalog.json": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      LICENSE: {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/assets/external-skills/stable/licenses/mattpocock-skills-LICENSE":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5",
        },
      "onboard/runtime/assets/external-skills/stable/licenses/ponytail-LICENSE":
        {
          license: "MIT",
          owner: "ponytail",
          sha256:
            "fb1bc6909ac3ef82d5c22106e32ef682b0cff66788fa915fb9b53b15c9d2f3ab",
        },
      "onboard/runtime/assets/external-skills/stable/licenses/ui-ux-pro-max-skill-LICENSE":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "738f69dfa83db5c347c678fb9d90e560877059f0de93a327c39001bff92dc014",
        },
      "onboard/runtime/assets/external-skills/stable/MANIFEST.json": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/assets/external-skills/stable/skills/codebase-design/agents/openai.yaml":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "edebc9e4fcfe102114012575eaa9600b9b5fd08c311664f389c36e7bc717740f",
        },
      "onboard/runtime/assets/external-skills/stable/skills/codebase-design/DEEPENING.md":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "f3dd099ce99289bd213914d8ee3e2429b78309c3957ca4583f7659551b1d53c1",
        },
      "onboard/runtime/assets/external-skills/stable/skills/codebase-design/DESIGN-IT-TWICE.md":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "8e740bf98446dbd4dfdc132ac4346d9a7eedaf93de6a495889171cf7f99f16bd",
        },
      "onboard/runtime/assets/external-skills/stable/skills/codebase-design/SKILL.md":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "2c20617f87ec8af6a434859f381b2f061a69b530444e74eb39e78bb016a6d1e2",
        },
      "onboard/runtime/assets/external-skills/stable/skills/diagnosing-bugs/agents/openai.yaml":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "3e430dbe4334a87597488c060cb3dc3786bb00c9182877d6f5ec41f62490e90b",
        },
      "onboard/runtime/assets/external-skills/stable/skills/diagnosing-bugs/scripts/hitl-loop.template.sh":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "35103539fc36873eea36074769ad454f9379d6fc8b2dc0e26ce987fd3bfe5503",
        },
      "onboard/runtime/assets/external-skills/stable/skills/diagnosing-bugs/SKILL.md":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "77f3cf31bc99b2f49af943222526531fcc9fc41d047626d3640e875e85af3e84",
        },
      "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/ADR-FORMAT.md":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "944c92aa790e8fbdc9199640b170979abb8a34ba8d0fe18c2a01a63bce140ca0",
        },
      "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/agents/openai.yaml":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "f6bf2aa996c6e6f53fdd0708e18a0d16a56aed8322cca59fedbe3c0d2c75f06b",
        },
      "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/CONTEXT-FORMAT.md":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "17ab16ce783e4d2801ee52fd9acdf550cbf44de65ae76797a93943bbedf22a13",
        },
      "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/SKILL.md":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "327a2b50620e2fd70abc6893cd6965e76b20f8d0adb0dc2c8d5eb3845efb643e",
        },
      "onboard/runtime/assets/external-skills/stable/skills/grill-me/agents/openai.yaml":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "c061e39c3e0f9d865fb1b97556d485704af2a8a58f4b8221a8917a5c2074a32b",
        },
      "onboard/runtime/assets/external-skills/stable/skills/grill-me/SKILL.md":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "caaf8b8de1684f96e26b28f3c29189db5c89cce4b73e1c93d86164f66ef88637",
        },
      "onboard/runtime/assets/external-skills/stable/skills/grill-with-docs/agents/openai.yaml":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "94cd0ab161fb468a836349f5ed482ba58ce8e709a05c57ce533d739dbd35cca9",
        },
      "onboard/runtime/assets/external-skills/stable/skills/grill-with-docs/SKILL.md":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "7de372c13488f1ee96cc11cd8907b56b6809cc93eef776eeddd37de6b6cbe3fe",
        },
      "onboard/runtime/assets/external-skills/stable/skills/grilling/agents/openai.yaml":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "1411d7df7d99b7e621a1ff8283c8133cc2464be63d064e52d8ce169c6800ee9b",
        },
      "onboard/runtime/assets/external-skills/stable/skills/grilling/SKILL.md":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "10ff989e7498b23b5acb49d5048f11dcd906757d2f79c5cdf8a00001381296f2",
        },
      "onboard/runtime/assets/external-skills/stable/skills/handoff/agents/openai.yaml":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "5c479fd562c691851690e8b18c8501045bef0943c10743d636b2fae26add1d28",
        },
      "onboard/runtime/assets/external-skills/stable/skills/handoff/SKILL.md": {
        license: "MIT",
        owner: "mattpocock-skills",
        sha256:
          "7c62de979fdc7ac32fb5ddb2146156c917f80ee070d30fadc9d40343c4b6ed25",
      },
      "onboard/runtime/assets/external-skills/stable/skills/ponytail-audit/SKILL.md":
        {
          license: "MIT",
          owner: "ponytail",
          sha256:
            "5560b8e383dbe2ddfddc873a1e2bf2e586e23e0cd7d995537482b2315331f6d1",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ponytail-debt/SKILL.md":
        {
          license: "MIT",
          owner: "ponytail",
          sha256:
            "c84fba75f0ca12bfe83f9a78ea02fd125c5dd3f1fbb18124105a489937f284e6",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ponytail-review/SKILL.md":
        {
          license: "MIT",
          owner: "ponytail",
          sha256:
            "40df33b58fc6ef889b93585733feb9566b76e9586efa7f376785c1e995197ac0",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ponytail/SKILL.md":
        {
          license: "MIT",
          owner: "ponytail",
          sha256:
            "1316a2f3f95741d2300b116fe0c2d81ce4a9568656ed0a62643f54aaf09957f2",
        },
      "onboard/runtime/assets/external-skills/stable/skills/tdd/agents/openai.yaml":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "ea6f01cf1b8c06a4b0f5b649d74b1b8ce8685e72af1b38d70d877693e092af0b",
        },
      "onboard/runtime/assets/external-skills/stable/skills/tdd/mocking.md": {
        license: "MIT",
        owner: "mattpocock-skills",
        sha256:
          "3ceb807fdf4a47d6a93d4d9a891e5ba6d362a6247bd08adc451feebfc17361ef",
      },
      "onboard/runtime/assets/external-skills/stable/skills/tdd/SKILL.md": {
        license: "MIT",
        owner: "mattpocock-skills",
        sha256:
          "cb01f66bebfaa25fa1f88e6b7e769cd9fd9f35b1120b8563749820738814c927",
      },
      "onboard/runtime/assets/external-skills/stable/skills/tdd/tests.md": {
        license: "MIT",
        owner: "mattpocock-skills",
        sha256:
          "859f9e592c188fda4fc7277dd180e4ce9c7a2e13f6efe1f6f29eccc9d28c106a",
      },
      "onboard/runtime/assets/external-skills/stable/skills/to-spec/agents/openai.yaml":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "1c5b4d1e3d8e52287ef19cc2742fdbbfae1914ac75d33af3e4c8174f08cc55bb",
        },
      "onboard/runtime/assets/external-skills/stable/skills/to-spec/SKILL.md": {
        license: "MIT",
        owner: "mattpocock-skills",
        sha256:
          "43ad9cf318e5e7d3d1fa360253a37021796dc87a0c2e595ad262661a10f85088",
      },
      "onboard/runtime/assets/external-skills/stable/skills/to-tickets/agents/openai.yaml":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "21bc6215fffcd7614e9f772bb1760e87cc5fc7dcc707e7d282bc9414267a6090",
        },
      "onboard/runtime/assets/external-skills/stable/skills/to-tickets/SKILL.md":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "5c9fba69845c2519b9b35b9af42ae5142c21f8ca15ac2123dc2722002c8058ae",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/app-interface.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "331e7cf2c0b222d80c566c5f255c63cb339f65bfd02e471a720f28e4864a9f08",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/catalog-summary.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "a257ccd1f85ff5e59f566a069d4c8ba91c90db3f88fc6bc7323a1cb4e9e37421",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/charts.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "4115cf1120680f2cedef0676cb648f30c7ef4699e2a947535d4113e71ed3b12a",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/colors.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "8162429222bce22df62b564085946a30d07cc9722c58d0a3a494bd0d1d00841c",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/data-provenance.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "e82fb33ed49375a300e93d9c11ccd1c1493c999e84ee7ee295e527634786e2e0",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/google-font-licenses.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "35688523f2955795caa1a47c53b83099e60c1708461476f9cc3a050cf3b0148a",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/google-fonts.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "1c8c3b2ea1faf6a1012da463756def8b3889db33f2226f0343bb4daa80307d03",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/icons.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "50816c6012030178195a16ee481ebf58b47bd985d70e8ec58886cc83f6eddafc",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/landing.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "9a2edd3bb676c2a58f00ade7a062e285222d4297bfd847c8d5b056f0dbbf52d0",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/motion.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "381affe8df8ea1f66fbbda2598827f9f54299107bbe6a1b4e9b68f6b62091ceb",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/phosphor-icons-upstream.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "2399325233b277b5c97a80e6a5e8941154f5d057beee4e7613db87c87d700236",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/products.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "42473f75e8dde5987bdf89ce55d8c168091b80a356cae691dd60247d80720b70",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/react-performance.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "3d925802539abac5afeb63ae8aa1960b7229ad271b3a47caed40ab2d97ad0734",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/angular.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "704be83f2bad30c7e6de01afb113ffa01e0c458762f48b7102f31ba2367b5553",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/astro.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "2c2f55fadaafc05e04cc321c8194a1a28b656e6757fe2ba316f41b16428299c6",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/avalonia.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "442fca14675a020683473e7e49f08abb27b9df0765c80efe54aef61f1a4ac258",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/flutter.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "64dba0ac17349f28bce517a0f5f48c54d9ed2e487ec0c0258303463b382f41a0",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/html-tailwind.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "d05a581d20af57b8ca0104a6d31d90a07c437d500662a96c3029fc2f9a4678ee",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/javafx.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "2e819b8d5abdd23ad4dae0991650fdb57af497aabd68b37463aa9c442944c869",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/jetpack-compose.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "699de218b286948eaec7d15767b6e1350ee299167e49bf476d82e3ff58724e0a",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/laravel.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "854ea4daa5fc61292d22235ad33b49ba3fe22423c3de8d3cb03758ffed3b59f9",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/nextjs.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "ecd2c27b2ea0127d203ae726060efcdd7335b5e83f96b99e4f3befbbfeebd5a4",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/nuxt-ui.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "c36ee8470926b4a0748d241363c71664c9969c2edbc62f7f72de0db73880fac6",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/nuxtjs.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "3d9b54ed2d151bd9c86e9e5609b8a6f88a00c4c52fa601a30af96c49b2c4d176",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/react-native.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "ba31dd9c0c04da6bc02a74448bf121f9c0728ae5ba3b4d47b487778b0a1135b5",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/react.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "2d2b9c198e875106a30f7ee68341a9ee0033cad60a7e130cf23152783e08aeda",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/shadcn.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "e56cfde5b74907836ac3582a4779d5b7f3d206a702ab81b8669a1b668c3eeb51",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/svelte.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "f6e379ba802941ba26b01d4ffbe3cd39120f2587659a1d93851c707f66bc13db",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/swiftui.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "bdd9231ff3ad658f4e7c063e1eb49df2fd09ac8d90631a86df899b39833b9623",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/threejs.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "97542e0ba34915a0ff7578be20e1619495df47c95c8c1c39b83e3785e1de771f",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/uno.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "a0474363e4225b5367214d5675fd3e075f137026f9500f0d04357882ef4f6d48",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/uwp.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "c409f08c1fbba1f1029f1acaa554e7b4471cc85517a5751c9f2e62465badcd5c",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/vue.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "b655f1ebb9dff2652d15981f31b1784c8a6d4759efd2815a14f3088257569f95",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/winui.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "e676dc1c13ee6c205c40b0746f1335150a346c7a49a0616d2545bc3d2c930c85",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/wpf.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "9781a9950b20333637b30a02e498b7efca21b618a3eeb8665836f3ac6e974da7",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/styles.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "a93a4d9d7025856575d7b7583bda020be9043013432c5af7c58af9dbdfb206b7",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/typography.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "321fc446e89024488ebae96dda93efc4d2307bd8bddb240857ad51364f6782c8",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/ui-reasoning.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "f0774dd741cecdad5eec842034bd6d5e9ea50e9f220a1910069748daa0bb8e9a",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/ux-guidelines.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "ff81ec613f70ba9fc3fcce52dbe4ae35d44b2079dbe6dc066d2d6e38c28facd5",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/references/pro-rules.md":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "d28442d61c310b49c054a4ea736f89fb3008beebdbbc38c4b3a540b8f7fadf23",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/references/quick-reference.md":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "0609bc7c89dacb40472465d8fc14257b56b2c43439660fc8d6fa3b8c022e1876",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/core.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "e544826963efefce3c59b65e18d83d92a5baf571f05458025bf1fa9021eced42",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/design_system.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "6a94743c3362c9c7e6d1450b94f4014d9ea752e7b4e151f6f0bdb217e0544bf7",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/reasoning_contract.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "b8bac1af82aa280d3e06f00aabaeac4337e632996b07fed874e2b6ee6e9c5913",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/search.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "d54e648fe0ec2932cac66684220cc17be4bd4b4eba1d23d3195d509d398db374",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-api.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "22d8dc81a7d6827b7e8b64b53e7d184210fb9759e8e294e0d5133c81cc460176",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-catalog.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "c608ad5c4084ebc50a4bbbfb69ea2456c01fd5519c457e18410fffd250ae948f",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-existing.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "4e0761b839dc6b2187a370e82eddc0aed8a7ff10c09e28dd814bb3656dac595b",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-metadata.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "30bffc29ae348416a2de2f9c6c418e768e4578f136b0f4bac5d2f70124f2e9ba",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-overrides.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "6243a48a4619986768c4628e2d0c98ff195beba71ba9be5df8f0c52fc6d90c0b",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/icons-curated.csv":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "68362c9a700c13b96f000784a0198c1c7e117a7088a01c85744e44233038fe9d",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-core.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "ae4d0bb076240824e1b643c2270d1f8cc0952a69502ec1e622b7dedd85b930bb",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-package.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "500588c757d6de03e3d7e69b27a8b8b1f88ccf6bb0333e4c1e9b0d6a4f112475",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-react-exports.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "d79f2ee0afdbc2f87776733e145df3538a16a25d7c2fba0056bb48295dad0ded",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-react-package.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "1c57a1d76bcc0cdd3632d4c18b9c0e79576b4591df39831c9607e5d0eb4f2cec",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/relevance-baseline.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "38398452985116e74e31bd6bccca0f4decd1bbfe4eebc1ac99f7a1836baaf77f",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/relevance-cases.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "e77d36eebbf6ddc2860946a02cdb659351da6c09f2688f1ed30939a418099646",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/relevance-thresholds.json":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "9d738e11c6b82fecc8d0946e7b38515518ded5ed3294a7eb19a021c4edb5b57d",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_catalog_refresh.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "3e2ca5d12702318f641ae62d0c14f22a3bcc84d84e79b863c0e947d475604adb",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_catalog_summary_line_endings.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "fa6ff09f0ec2c99013588c77397f5082dddebe8f467e94c5f8378ec9595f4989",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_core_data_quality.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "3ffc6b4905c9ea26d7ac4527ab154d153584231aee71b2ae4bd017977fa09cc5",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_core.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "3527fe2f4b852f69f07c17ddc0d615d9a6e025c924e45a33985579a94a8d2118",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_data_contracts.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "0360d6e10080c0bca214f2b0bbad582ba50702a542ce21013351aca54938df3a",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_design_system_mode.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "517ba1ba6195c94811126d1162139c51aff77fc68c3e320c7bb6c1e89e76bc9b",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_design_system_stack.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "83d09ffe8cfbf7b265f362129f061dfe8e5e167ce5db43adaead197cabc9ca38",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_native_desktop_stack_freshness.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "904f90bc6d364763673fa6067d98a4227d535760fa8b6d26abe22208176997ca",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_relevance_evaluator.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "2fe56a4d6fe5fff15ff592274b0eeaba925146cefea6c0fa29d8f1b77c9aca1f",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_skill_script_paths.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "7cec24b94be771bc60bc84f8993e614bb16d4047930e1dd3d3bed91628311d44",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_style_taxonomy.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "cd14d0092e8a454d213aa104b53e4e70ba698491fa00fde9fdec5ca8a3d70011",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_text_layout_resilience.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "b51d32ee8a15505b87cb81957fb2d1b385e041e8beb4463c311d236bfd29ebd4",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_web_stack_freshness.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "becc5fa40e7516613d4e9930f226aa483e3796090c17cb16542c93d1927e680d",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/validate_data.py":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "a599aa256049cf30954d1f164721b99e453eb7e4cb8241bcab2d5573e6cf58b8",
        },
      "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/SKILL.md":
        {
          license: "MIT",
          owner: "ui-ux-pro-max-skill",
          sha256:
            "ea087c341bfb5b23195c7302027268ede86da802554c18a5c4896a6017b439f9",
        },
      "onboard/runtime/assets/external-skills/stable/skills/writing-for-agents/agents/openai.yaml":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "eacb24b2a618cfb81dacb0416f4fdd75ddf3a8060f8ddb99aae1b1e301907e4b",
        },
      "onboard/runtime/assets/external-skills/stable/skills/writing-for-agents/SKILL-MECHANICS.md":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "c768e6307c7c10728c401c213f2c4ba71c542127eeb7ad2956aabd15a0fa0059",
        },
      "onboard/runtime/assets/external-skills/stable/skills/writing-for-agents/SKILL.md":
        {
          license: "MIT",
          owner: "mattpocock-skills",
          sha256:
            "551adca942227b44192edba88acd4e8db911f0121ce58ad16944ccf6a896a74a",
        },
      "onboard/runtime/assets/external-skills/stable/THIRD_PARTY_NOTICES.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/assets/graft-build-policy.json": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/assets/graft-hook-entry.mjs": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/assets/graft-instructions.txt": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/assets/migration-legacy-ownership.json": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/assets/migration-local-ignore.txt": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/assets/migration-paused-agents.txt": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/assets/routing-approval.pub": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/assets/runtime-lineage.json": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/assets/runtime-lineage.pub": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/catalog.json": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/catalog.schema.json": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/examples/catalog.minimal.json": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/LICENSE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/NOTICE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "8eba762aba6bfaea156420944c443c487ed36ea2471099f42dd834121f9545e4",
      },
      "onboard/runtime/onboard-contracts.schema.json": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/requirements.txt": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/graft_runtime.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/onboard_arguments.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/onboard_contracts.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/onboard.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_backup_retention.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_cleanup_legacy.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_cleanup_targets.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_cleanup_upgrade.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_codex_wiring.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_graft_deployment.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_graft_entry.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_handoff.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_identity.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_migration_files.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_migration_legacy.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_migration_plan.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_migration_verify.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_migration.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_omp_sources.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_omp_wiring.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_probe_links.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_project.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_reconciliation.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_recovery.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_task_document.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_task_routing.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_task_state.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_trellis_uninstall.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_upgrade_cli.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_upgrade_hosts.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_upgrade_inventory.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_upgrade_paths.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/scripts/sbtd_upgrade.py": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/project/gitignore.template": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/book-ddd-distilled-modeling/LICENSE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/templates/skills/book-ddd-distilled-modeling/NOTICE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "8eba762aba6bfaea156420944c443c487ed36ea2471099f42dd834121f9545e4",
      },
      "onboard/runtime/templates/skills/book-ddd-distilled-modeling/SKILL.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/book-ddia-data-design/LICENSE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/templates/skills/book-ddia-data-design/NOTICE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "8eba762aba6bfaea156420944c443c487ed36ea2471099f42dd834121f9545e4",
      },
      "onboard/runtime/templates/skills/book-ddia-data-design/SKILL.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/book-legacy-change-safety/LICENSE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/templates/skills/book-legacy-change-safety/NOTICE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "8eba762aba6bfaea156420944c443c487ed36ea2471099f42dd834121f9545e4",
      },
      "onboard/runtime/templates/skills/book-legacy-change-safety/SKILL.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/book-refactoring-pass/LICENSE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/templates/skills/book-refactoring-pass/NOTICE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "8eba762aba6bfaea156420944c443c487ed36ea2471099f42dd834121f9545e4",
      },
      "onboard/runtime/templates/skills/book-refactoring-pass/SKILL.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/book-release-readiness/LICENSE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/templates/skills/book-release-readiness/NOTICE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "8eba762aba6bfaea156420944c443c487ed36ea2471099f42dd834121f9545e4",
      },
      "onboard/runtime/templates/skills/book-release-readiness/SKILL.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/gherkin-bdd/LICENSE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/templates/skills/gherkin-bdd/NOTICE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "8eba762aba6bfaea156420944c443c487ed36ea2471099f42dd834121f9545e4",
      },
      "onboard/runtime/templates/skills/gherkin-bdd/SKILL.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/knowledge-base-integration/LICENSE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/templates/skills/knowledge-base-integration/NOTICE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "8eba762aba6bfaea156420944c443c487ed36ea2471099f42dd834121f9545e4",
      },
      "onboard/runtime/templates/skills/knowledge-base-integration/references/artifact-manifest.schema.json":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/references/deployment-manifest.example.yaml":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/references/deployment-manifest.schema.json":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/references/evidence-decision.schema.json":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/references/metrics.schema.json":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/references/product.example.yaml":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/references/product.schema.json":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/references/revision-set.schema.json":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/references/runner-job.schema.json":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/references/runner-result.schema.json":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/references/runtime-contract.md":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/references/workspace.local.example.yaml":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/references/workspace.schema.json":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/requirements.txt":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/scripts/knowledge_base_p1.py":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/knowledge-base-integration/SKILL.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/lessons-record/LICENSE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/templates/skills/lessons-record/NOTICE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "8eba762aba6bfaea156420944c443c487ed36ea2471099f42dd834121f9545e4",
      },
      "onboard/runtime/templates/skills/lessons-record/references/identity-migration.md":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/lessons-record/SKILL.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/maestro-mobile-e2e/LICENSE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/templates/skills/maestro-mobile-e2e/NOTICE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "8eba762aba6bfaea156420944c443c487ed36ea2471099f42dd834121f9545e4",
      },
      "onboard/runtime/templates/skills/maestro-mobile-e2e/references/ios-real-device-setup.md":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/maestro-mobile-e2e/references/lessons-index.md":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/maestro-mobile-e2e/SKILL.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/project-validation/LICENSE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/templates/skills/project-validation/NOTICE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "8eba762aba6bfaea156420944c443c487ed36ea2471099f42dd834121f9545e4",
      },
      "onboard/runtime/templates/skills/project-validation/references/run-summary.zh-CN.md.template":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/project-validation/references/validation-evidence-contract.md":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/project-validation/references/validation-evidence.schema.json":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/project-validation/references/validation-evidence.v2.schema.json":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/project-validation/requirements.txt": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/project-validation/scripts/validate_validation_evidence.py":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/project-validation/SKILL.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/sbtd-task/LICENSE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/templates/skills/sbtd-task/NOTICE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "8eba762aba6bfaea156420944c443c487ed36ea2471099f42dd834121f9545e4",
      },
      "onboard/runtime/templates/skills/sbtd-task/references/handoff.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/sbtd-task/references/methods.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/sbtd-task/references/presentation.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/sbtd-task/references/state.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/sbtd-task/references/strict.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/sbtd-task/references/task-data.schema.json":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/sbtd-task/references/tooling.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/sbtd-task/SKILL.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/seo-geo/LICENSE": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/templates/skills/seo-geo/NOTICE": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "be9cb9e085b8ca791638a4ee50d9f72876ebdd4a570df4439b30c4fa1d4562a2",
      },
      "onboard/runtime/templates/skills/seo-geo/references/geo-research.md": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "901516a3b7964aee88297e0f52e517abef6111150ba781d27e5e9e76c08be1c8",
      },
      "onboard/runtime/templates/skills/seo-geo/references/google-docs-summary.md":
        {
          license: "Apache-2.0",
          owner:
            "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
          sha256:
            "214544d0b4891c1f3613727b73da23be2361d83214190b7455a058dd0c784638",
        },
      "onboard/runtime/templates/skills/seo-geo/references/platform-algorithms.md":
        {
          license: "Apache-2.0",
          owner:
            "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
          sha256:
            "ad2f55b54e74be411f207f2662626beea0f8770c9e92fd3f1c5d14fee3faacb6",
        },
      "onboard/runtime/templates/skills/seo-geo/references/schema-templates.md":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/seo-geo/references/seo-checklist.md": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "36e83bdccdaf831dd7a3fe9587b83f03f32444faa2e2b93ef75f0dda290c19cb",
      },
      "onboard/runtime/templates/skills/seo-geo/references/tools-and-apis.md": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "a9519882c35519e28b7668436e7cbf291185ab57a0169468d19d261bb49867ff",
      },
      "onboard/runtime/templates/skills/seo-geo/scripts/autocomplete_ideas.py":
        {
          license: "Apache-2.0",
          owner:
            "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
          sha256:
            "7d2ea86f48f39b7ef8d67f2128564d66583120d09d47cdc95613fe8e0d3a5b02",
        },
      "onboard/runtime/templates/skills/seo-geo/scripts/backlinks.py": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "d2163c09008166531680ebe2c1bf5fd799ecc654e6e2887a56c6a4f83650631a",
      },
      "onboard/runtime/templates/skills/seo-geo/scripts/competitor_gap.py": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "76a9783fbecd7ddd8792f3af7dcec51e3e8d27318171d7a852ea99f53453047d",
      },
      "onboard/runtime/templates/skills/seo-geo/scripts/credential.py": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "81a0c5ee938b71e412564c88da030cc42c4f8ef283a0ab02beaf09f31733436b",
      },
      "onboard/runtime/templates/skills/seo-geo/scripts/dataforseo_api.py": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "8e5918619cdee675527dae9384de26ba2242a54d31016c6867fff2fcb0acc9ef",
      },
      "onboard/runtime/templates/skills/seo-geo/scripts/domain_overview.py": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "4d167381a6e2111de636858d7fefe7054fcf69e70b5bc699d095566c8b825874",
      },
      "onboard/runtime/templates/skills/seo-geo/scripts/keyword_research.py": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "b498b35a2103ce797e945d9ff6287c056e5c6bc5bfc6cac6abba9d5c2e9b291a",
      },
      "onboard/runtime/templates/skills/seo-geo/scripts/related_keywords.py": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "9f6171d36c739f1929ef0e0e06029ab95e36dd66519f048443d8a97e78ef2a21",
      },
      "onboard/runtime/templates/skills/seo-geo/scripts/seo_audit.py": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "fa61627048a995f309bff42a1ef507ba4b52fc050ca5446cce3817151e0a2700",
      },
      "onboard/runtime/templates/skills/seo-geo/scripts/serp_analysis.py": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "2d2459a9027be63d988f420373ad312181178b230ab079dc407764581904acda",
      },
      "onboard/runtime/templates/skills/seo-geo/SKILL.md": {
        license: "Apache-2.0",
        owner:
          "ReScienceLab/opc-skills@ab75cf514281af371962c3a8449cb2a3761fd2b9",
        sha256:
          "9f18b511397b5b39d2ed774c4af9a481f675d593ef84d0a6baf8077da2ecfe3c",
      },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/agents/openai.yaml":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/auth-fixture.ts.template":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/github-actions-e2e.yml.template":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/package-scripts.json.template":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/page-object.ts.template":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/page-spec.ts.template":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/playwright.config.ts.template":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/summary.zh-CN.md.template":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/gitignore.template":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/LICENSE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/NOTICE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "8eba762aba6bfaea156420944c443c487ed36ea2471099f42dd834121f9545e4",
      },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/README.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/README.zh-CN.md":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/references/coverage-rubric.md":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/references/output-contract.md":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/scripts/analyze_failures.py":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/scripts/audit_selectors.py":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/scripts/check_coverage.py":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/scripts/generate_manifest.py":
        {
          license: "Apache-2.0",
          owner: "first-party",
        },
      "onboard/runtime/templates/skills/web-ui-autotest-generator/SKILL.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "onboard/runtime/upgrade.schema.json": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "THIRD_PARTY_NOTICES.md": {
        license: "Apache-2.0",
        owner: "first-party",
      },
      "third-party/sbtd-workflow-onboard/LICENSE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
      },
      "third-party/sbtd-workflow-onboard/NOTICE": {
        license: "Apache-2.0",
        owner: "first-party",
        sha256:
          "8eba762aba6bfaea156420944c443c487ed36ea2471099f42dd834121f9545e4",
      },
    },
    overlayPaths: [
      "AGENTS.global.md",
      "AGENTS.project-root.md",
      "onboard/runtime/catalog.json",
      "onboard/runtime/catalog.schema.json",
      "onboard/runtime/templates/project/gitignore.template",
      "onboard/runtime/templates/skills/gherkin-bdd/SKILL.md",
      "onboard/runtime/templates/skills/sbtd-task/references/presentation.md",
      "onboard/runtime/templates/skills/seo-geo/references/schema-templates.md",
      "onboard/runtime/templates/skills/web-ui-autotest-generator/README.md",
      "onboard/runtime/templates/skills/web-ui-autotest-generator/README.zh-CN.md",
    ],
    ledger: {
      schemaVersion: 1,
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
          repository: "mattpocock-skills",
          sourceSubpath: "skills/productivity/grilling",
          stablePath: "skills/grilling",
          treeSha256:
            "b0af4cb93507011cab704853dc540ae142dec2a1256d374a38f4f196a04f7b50",
        },
        "domain-modeling": {
          repository: "mattpocock-skills",
          sourceSubpath: "skills/engineering/domain-modeling",
          stablePath: "skills/domain-modeling",
          treeSha256:
            "731ecd11825453ec3d813ac26e7a082bb458bc332781c6dba18d7004468139d7",
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
          repository: "mattpocock-skills",
          sourceSubpath: "skills/engineering/to-tickets",
          stablePath: "skills/to-tickets",
          treeSha256:
            "7d82d3f4b50f4f57bafc8e361cdf6b06fde6f3b940bbd13199a184e98f0d34c4",
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
    topNoticeParts: {
      beforeRevision:
        "# Third-Party Notices\n\n## SBTD Workflow Onboard\n\n- Source: https://github.com/KunoLu/640-skills@",
      betweenRevisionAndStableSet:
        "\n- License: Apache-2.0\n- Retained license: onboard/runtime/LICENSE\n- Retained notice: onboard/runtime/NOTICE\n\n## Stable External Skills (stable set ",
      afterStableSet:
        ')\n\n### mattpocock-skills\n\n- Source: https://github.com/mattpocock/skills.git@3cca18b368ae95cdbdebbff572ccafa662551015\n- License: MIT\n- Retained license: onboard/runtime/assets/external-skills/stable/licenses/mattpocock-skills-LICENSE\n\n### ui-ux-pro-max-skill\n\n- Source: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.git@7f69fed6a2717900085f1bc3b263721f8ba025e2\n- License: MIT\n- Retained license: onboard/runtime/assets/external-skills/stable/licenses/ui-ux-pro-max-skill-LICENSE\n\n### ponytail\n\n- Source: https://github.com/DietrichGebert/ponytail.git@356918eba965ee1eac64bd3a7f0dd02108350de5\n- License: MIT\n- Retained license: onboard/runtime/assets/external-skills/stable/licenses/ponytail-LICENSE\n\n## Retained metadata attribution\n\n### @phosphor-icons/core@2.1.1\n\n- Applies to npm package member (relative to package root): kit/onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/phosphor-icons-upstream.json\n- Scope: 1512 metadata records; no SVG assets.\n- Source archive: https://registry.npmjs.org/@phosphor-icons/core/-/core-2.1.1.tgz\n- Source archive SHA256: 313332be6190b724da24107addd781799b48bf76b13963f24501112ffe1baadd\n\nMIT License\r\n\r\nCopyright (c) 2023 Phosphor Icons\r\n\r\nPermission is hereby granted, free of charge, to any person obtaining a copy\r\nof this software and associated documentation files (the "Software"), to deal\r\nin the Software without restriction, including without limitation the rights\r\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\r\ncopies of the Software, and to permit persons to whom the Software is\r\nfurnished to do so, subject to the following conditions:\r\n\r\nThe above copyright notice and this permission notice shall be included in all\r\ncopies or substantial portions of the Software.\r\n\r\nTHE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\r\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\r\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\r\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\r\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\r\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\r\nSOFTWARE.\r\n',
    },
    stableNotice:
      '# Stable External Skills\n\nThis directory contains unmodified snapshots of the External Skills used by\nthe SBTD Onboard workflow. `MANIFEST.json` records the exact upstream commit,\nsource subpath, content digest, and license files for every snapshot.\n\nThe snapshots are installation fallbacks, not local forks. Update them only\nthrough an explicit stable promotion that preserves upstream content and\nrefreshes the manifest digests and third-party notices.\n\n| Repository | License | Included notices |\n|---|---|---|\n| `mattpocock/skills` | MIT | `licenses/mattpocock-skills-LICENSE` |\n| `nextlevelbuilder/ui-ux-pro-max-skill` | MIT | `licenses/ui-ux-pro-max-skill-LICENSE` |\n| `DietrichGebert/ponytail` | MIT | `licenses/ponytail-LICENSE` |\n\n## Retained metadata attribution\n\n### @phosphor-icons/core@2.1.1\n\n- Applies to npm package member (relative to package root): kit/onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/phosphor-icons-upstream.json\n- Scope: 1512 metadata records; no SVG assets.\n- Source archive: https://registry.npmjs.org/@phosphor-icons/core/-/core-2.1.1.tgz\n- Source archive SHA256: 313332be6190b724da24107addd781799b48bf76b13963f24501112ffe1baadd\n\nMIT License\r\n\r\nCopyright (c) 2023 Phosphor Icons\r\n\r\nPermission is hereby granted, free of charge, to any person obtaining a copy\r\nof this software and associated documentation files (the "Software"), to deal\r\nin the Software without restriction, including without limitation the rights\r\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\r\ncopies of the Software, and to permit persons to whom the Software is\r\nfurnished to do so, subject to the following conditions:\r\n\r\nThe above copyright notice and this permission notice shall be included in all\r\ncopies or substantial portions of the Software.\r\n\r\nTHE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\r\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\r\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\r\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\r\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\r\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\r\nSOFTWARE.\r\n',
    projection: {
      policyVersion: 1,
      counts: {
        included: 261,
        omitted: 81,
        replaced: 10,
      },
    },
  };
  return cachedProfile;
}
