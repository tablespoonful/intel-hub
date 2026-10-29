// Module types for files bundled by the [[rules]] in wrangler.toml.

declare module "*.png" {
  const data: ArrayBuffer;
  export default data;
}

declare module "*.svg" {
  const text: string;
  export default text;
}
