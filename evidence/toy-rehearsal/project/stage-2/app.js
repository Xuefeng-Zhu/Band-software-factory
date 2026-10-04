"use strict";

const number = document.querySelector('[data-testid="counter-value"]');
const button = document.querySelector('[data-testid="increment-button"]');
const status = document.querySelector('[role="status"]');
let pending = true;
let ready = false;

async function readValue(path, method) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const options = { method, signal: controller.signal, cache: "no-store" };
    if (method === "POST") {
      options.headers = { "Content-Type": "application/json" };
      options.body = "{}";
    }
    const response = await fetch(path, options);
    if (!response.ok) throw new Error("Unsuccessful response");
    const payload = await response.json();
    if (!payload || !Number.isSafeInteger(payload.value)) {
      throw new Error("Invalid counter value");
    }
    return payload.value;
  } finally {
    clearTimeout(timer);
  }
}

async function update(initial) {
  if (!initial && (pending || !ready)) return;
  const hadFocus = document.activeElement === button;
  pending = true;
  button.disabled = true;
  status.textContent = initial ? "Loading counter…" : "Adding 1…";
  try {
    const value = await readValue(initial ? "/counter" : "/counter/increment", initial ? "GET" : "POST");
    number.textContent = String(value);
    ready = true;
    status.textContent = initial ? "" : `Counter is now ${value}.`;
    button.disabled = false;
    if (hadFocus && document.activeElement === document.body) {
      button.focus({ preventScroll: true });
    }
  } catch {
    ready = false;
    status.classList.add("error");
    status.textContent = initial
      ? "Could not load the counter. Reload this page to try again."
      : "Could not confirm the update. The number shown is the last confirmed value. Reload this page to check the current value.";
  } finally {
    pending = false;
  }
}

button.addEventListener("click", () => update(false));
update(true);
