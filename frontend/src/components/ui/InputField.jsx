export default function InputField({
  label,
  type = "text",
  placeholder,
  error,
  autoComplete,
  ...rest
}) {
  const inputClassName = `w-full bg-slate-800 border text-white text-sm rounded-xl px-4 py-3 outline-none transition-all ${
    error
      ? "border-red-500"
      : "border-slate-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
  }`;

  return (
    <div>
      {label ? (
        <label className="block text-sm font-medium text-slate-300 mb-1.5">
          {label}
        </label>
      ) : null}

      <input
        type={type}
        placeholder={placeholder}
        autoComplete={autoComplete ?? (type === "password" ? "new-password" : "off")}
        className={inputClassName}
        {...rest}
      />

      {error ? <p className="text-red-500 text-xs mt-1.5">{error}</p> : null}
    </div>
  );
}
