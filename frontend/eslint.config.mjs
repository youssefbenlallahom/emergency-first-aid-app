import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

// eslint-config-next v16+ ships native Flat Config arrays.
export default require("eslint-config-next/core-web-vitals");
