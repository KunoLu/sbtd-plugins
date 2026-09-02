type T0Context = {
  systemPrompt: {
    section: (opts: { name: string; order: number; text: string }) => void;
  };
};

export const name = "dsh-sbtd";
export const inject = ["tools", "systemPrompt"] as const;

export function apply(ctx: T0Context): void {
  console.log("[dsh-sbtd] plugin loaded (T0 stub)");
  ctx.systemPrompt.section({ name: "sbtd", order: 50, text: "" });
}
