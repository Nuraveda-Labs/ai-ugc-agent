import { Config } from "@remotion/cli/config";
import path from "node:path";
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setConcurrency(2);
Config.setPublicDir(path.resolve(__dirname, "..", "output"));
