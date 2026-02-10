import { Toaster as SonnerToaster } from "sonner"

import { usePreferencesStore } from "@/store/preferencesStore"

const Toaster = () => {
  const resolvedTheme = usePreferencesStore((state) => state.resolvedTheme)

  return (
    <SonnerToaster
      theme={resolvedTheme}
      className="toaster group"
      richColors
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:rounded-xl group-[.toaster]:shadow-noble-lg group-[.toaster]:border group-[.toaster]:border-border/50 group-[.toaster]:bg-card group-[.toaster]:text-foreground",
          description: "group-[.toast]:text-muted-foreground",
          actionButton:
            "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton:
            "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
        },
      }}
    />
  )
}

export { Toaster }
