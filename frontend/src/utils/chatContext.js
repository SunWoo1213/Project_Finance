function safeDecode(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export function buildChatContext({ location, authState }) {
  const path = location?.pathname || "/";
  const detailMatch = path.match(/^\/detail\/(.+)$/);
  const marketMatch = path.match(/^\/market\/(.+)$/);
  const categoryMatch = path.match(/^\/category\/(.+)$/);
  const rawTicker = detailMatch?.[1] || marketMatch?.[1] || null;

  return {
    current_path: path,
    context: {
      ticker: rawTicker ? safeDecode(rawTicker) : null,
      category: categoryMatch?.[1] ? safeDecode(categoryMatch[1]) : null,
      authenticated: Boolean(authState?.token),
    },
  };
}
