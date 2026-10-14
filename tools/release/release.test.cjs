const assert = require("node:assert/strict");
const path = require("node:path");
const { test } = require("node:test");
const { pathToFileURL } = require("node:url");
const config = require("../../release.config.cjs");
const manifest = require("./package.json");
const lock = require("./package-lock.json");

const logger = { log() {}, success() {}, error() {} };

test("semantic-release loads the explicit root config instead of npm defaults", async () => {
	const { default: getConfig } = await import(
		new URL("./lib/get-config.js", pathToFileURL(require.resolve("semantic-release")))
	);
	const { options } = await getConfig(
		{ cwd: path.resolve(__dirname, "../.."), env: process.env, logger },
		{ extends: "./release.config.cjs" },
	);
	assert.deepEqual(options.branches, config.branches);
	assert.deepEqual(options.plugins, config.plugins);
});

test("only master and the three allowed release plugins are configured", () => {
	assert.deepEqual(config.branches, ["master"]);
	assert.equal(config.tagFormat, "v${version}");
	assert.equal(config.repositoryUrl, "https://github.com/Gopi-git-bit/New-logistic-.git");
	assert.deepEqual(
		config.plugins.map((entry) => (Array.isArray(entry) ? entry[0] : entry)),
		[
			require.resolve("@semantic-release/commit-analyzer"),
			require.resolve("@semantic-release/release-notes-generator"),
			require.resolve("@semantic-release/github"),
		],
	);
	assert.deepEqual(config.plugins[2][1], {
		successComment: false,
		failComment: false,
		failTitle: false,
		labels: false,
		releasedLabels: false,
	});
});

test("release dependencies are exact and match the installation lock", () => {
	assert.equal(manifest.private, true);
	assert.deepEqual(lock.packages[""].devDependencies, manifest.devDependencies);
	for (const [name, version] of Object.entries(manifest.devDependencies)) {
		assert.match(version, /^\d+\.\d+\.\d+$/);
		assert.equal(lock.packages[`node_modules/${name}`].version, version);
	}
});

test("Conventional Commits select patch, minor, major, or no release", async () => {
	const { analyzeCommits } = await import("@semantic-release/commit-analyzer");
	for (const [message, expected] of [
		["fix(api): handle an empty response", "patch"],
		["feat(portal): add a tracking view", "minor"],
		["feat(api): change response schema\n\nBREAKING CHANGE: remove the legacy field", "major"],
		["docs: explain release management", null],
		["chore: update tooling", null],
		["test: add coverage", null],
	]) {
		assert.equal(
			await analyzeCommits({}, { commits: [{ message, hash: "a".repeat(40) }], logger }),
			expected,
			message,
		);
	}
});

test("versioning starts at 1.0.0 or increments the previous release, not the manifest", async () => {
	const { default: getNextVersion } = await import(
		new URL("./lib/get-next-version.js", pathToFileURL(require.resolve("semantic-release")))
	);
	for (const [type, expected] of [
		["patch", "2.3.5"],
		["minor", "2.4.0"],
		["major", "3.0.0"],
	]) {
		const context = { branch: { type: "release" }, nextRelease: { type }, logger };
		assert.equal(getNextVersion({ ...context, lastRelease: {} }), "1.0.0");
		assert.equal(getNextVersion({ ...context, lastRelease: { version: "2.3.4" } }), expected);
	}
});

test("release notes are generated without publishing or credentials", async () => {
	const { generateNotes } = await import("@semantic-release/release-notes-generator");
	const notes = await generateNotes(
		{},
		{
			commits: [{ message: "fix(api): handle an empty response", hash: "a".repeat(40) }],
			lastRelease: {},
			nextRelease: { version: "1.0.0", gitTag: "v1.0.0" },
			options: { repositoryUrl: config.repositoryUrl },
			logger,
		},
	);
	assert.match(notes, /1\.0\.0/);
	assert.match(notes, /handle an empty response/);
});
