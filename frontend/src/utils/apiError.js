
export function getApiErrorMessage(error) {
  const detail = error.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = item.loc?.slice(1).join(".") || "Field";
        return `${field}: ${item.msg}`;
      })
      .join("; ");
  }

  if (error.code === "ECONNABORTED") {
    return "The request timed out. Please try again.";
  }

  if (!error.response) {
    return "Unable to connect to the server.";
  }

  return "Something went wrong. Please try again.";
}
