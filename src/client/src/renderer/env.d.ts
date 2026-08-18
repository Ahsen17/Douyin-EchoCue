interface Window {
  echocue: {
    platform: string;
    isDevelopment: boolean;
    window: {
      minimize: () => Promise<void>;
      toggleMaximize: () => Promise<void>;
      close: () => Promise<void>;
    };
    overlay: {
      open: (payload: {
        userName: string;
        commentDisplay: string;
        quickReply: string;
        cue: string;
        createdAt: string;
      }) => Promise<void>;
      update: (payload: {
        userName: string;
        commentDisplay: string;
        quickReply: string;
        cue: string;
        createdAt: string;
      }) => Promise<void>;
      hide: () => Promise<void>;
      show: () => Promise<void>;
      close: () => Promise<void>;
      setAlwaysOnTop: (enabled: boolean) => Promise<void>;
      setOpacity: (opacity: number) => Promise<void>;
      setIgnoreMouseEvents: (enabled: boolean) => Promise<void>;
      setFontScale: (fontScale: number) => Promise<void>;
      setSizeLevel: (sizeLevel: "small" | "medium" | "large") => Promise<void>;
      setTheme: (theme: "light" | "dark") => Promise<void>;
      onUpdate: (
        callback: (update: {
          payload: {
            userName: string;
            commentDisplay: string;
            quickReply: string;
            cue: string;
            createdAt: string;
          };
          fontScale: number;
          theme: "light" | "dark";
          opacity: number;
        }) => void,
      ) => () => void;
    };
    clientSettings: {
      get: () => Promise<{
        overlay: {
          alwaysOnTop: boolean;
          clickThrough: boolean;
          opacity: number;
          fontScale: number;
          theme: "light" | "dark";
          sizeLevel: "small" | "medium" | "large";
        };
        workspaceView: "overview" | "settings";
      }>;
      set: (settings: {
        overlay: {
          alwaysOnTop: boolean;
          clickThrough: boolean;
          opacity: number;
          fontScale: number;
          theme: "light" | "dark";
          sizeLevel: "small" | "medium" | "large";
        };
        workspaceView: "overview" | "settings";
      }) => Promise<void>;
    };
  };
}
