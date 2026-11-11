export function returnPath(value: unknown): string {
  return typeof value === "string" &&
    /^(?:\/|\/roles|\/hr|\/admin|\/rooms\/[A-Za-z0-9_-]{3,80}|\/sessions\/[A-Za-z0-9_-]{3,80}\/interview)$/.test(
      value,
    ) &&
    !/[\r\n]/.test(value)
    ? value
    : "/";
}
