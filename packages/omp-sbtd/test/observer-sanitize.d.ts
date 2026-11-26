// Only the static, cache-separated observer instance used by the sanitizer test.
declare module "*scripts/p0/host-event/observer.mjs?case=sanitize" {
  interface ObserverCommandContext {
    waitForIdle(): Promise<unknown>;
    readonly sessionManager: {
      getSessionId(): unknown;
      getEntries(): readonly Readonly<{ type?: unknown; id?: unknown }>[];
    };
  }

  interface ObserverHost {
    registerCommand(
      name: string,
      options: Readonly<{
        description: string;
        handler: (
          args: string,
          context: ObserverCommandContext,
        ) => Promise<void>;
      }>,
    ): void;
    on(name: string, handler: (event: unknown, context: unknown) => void): void;
  }

  export default function hostEventObserver(host: ObserverHost): void;
}
