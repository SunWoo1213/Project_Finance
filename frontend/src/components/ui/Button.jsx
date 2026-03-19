export default function Button({
  children,
  isLoading = false,
  variant = "primary",
  ...rest
}) {
  const baseClassName =
    "w-full flex justify-center items-center rounded-xl px-4 py-3 font-semibold text-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed";

  const variantClassName =
    variant === "primary" ? "bg-blue-600 hover:bg-blue-700 text-white" : "";

  return (
    <button
      type="button"
      className={`${baseClassName} ${variantClassName}`.trim()}
      disabled={isLoading || rest.disabled}
      {...rest}
    >
      {isLoading ? (
        <svg
          className="h-4 w-4 animate-spin text-white"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <circle
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="3"
            className="opacity-25"
          />
          <path
            d="M22 12a10 10 0 0 1-10 10"
            stroke="currentColor"
            strokeWidth="3"
            className="opacity-90"
          />
        </svg>
      ) : (
        children
      )}
    </button>
  );
}
