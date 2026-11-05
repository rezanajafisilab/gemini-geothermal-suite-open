// Where the models run, for "Resend on the CPU / GPU": the header owns the GPU | CPU switch, so it
// publishes what it shows (the device, whether there is a GPU, whether a reply is being written)
// and takes a request to switch.

export type DeviceChoice = "auto" | "cpu";

export interface DeviceState {
  device: DeviceChoice;
  gpu: boolean;
  busy: boolean;
}

let state: DeviceState = { device: "auto", gpu: true, busy: false };
const requests = new Set<(d: DeviceChoice) => void>();

/** The header: what its switch shows now. */
export function publishDevice(next: DeviceState): void {
  state = next;
}

export function deviceState(): DeviceState {
  return state;
}

/** The header: switch when a menu asks. */
export function onDeviceRequest(fn: (d: DeviceChoice) => void): () => void {
  requests.add(fn);
  return () => {
    requests.delete(fn);
  };
}

/** Switch where the models run (applies from the next run, as the header's switch does). */
export function requestDevice(d: DeviceChoice): void {
  state = { ...state, device: d };
  for (const fn of requests) fn(d);
}
