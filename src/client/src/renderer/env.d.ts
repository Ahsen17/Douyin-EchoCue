interface Window {
  echocue: {
    platform: string;
    isDevelopment: boolean;
    overlay: {
      open: (payload: {
        commentDisplay: string;
        quickReply: string;
        cue: string;
        createdAt: string;
      }) => Promise<void>;
      update: (payload: {
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
      setTheme: (theme: "light" | "dark") => Promise<void>;
      onUpdate: (
        callback: (update: {
          payload: {
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
  };
}
