const TOSS_PAYMENTS_SDK_URL = "https://js.tosspayments.com/v2/standard";

let sdkPromise = null;

export function loadTossPaymentsSdk() {
  if (window.TossPayments) {
    return Promise.resolve(window.TossPayments);
  }

  if (!sdkPromise) {
    sdkPromise = new Promise((resolve, reject) => {
      const existingScript = document.querySelector(`script[src="${TOSS_PAYMENTS_SDK_URL}"]`);
      if (existingScript) {
        existingScript.addEventListener("load", () => resolve(window.TossPayments), { once: true });
        existingScript.addEventListener("error", reject, { once: true });
        return;
      }

      const script = document.createElement("script");
      script.src = TOSS_PAYMENTS_SDK_URL;
      script.async = true;
      script.onload = () => resolve(window.TossPayments);
      script.onerror = () => reject(new Error("Toss Payments SDK load failed."));
      document.head.appendChild(script);
    });
  }

  return sdkPromise;
}
