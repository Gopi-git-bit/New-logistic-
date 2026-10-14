const path = require("node:path");

const plugin = (name) =>
	require.resolve(name, { paths: [path.join(__dirname, "tools/release")] });

module.exports = {
	branches: ["master"],
	repositoryUrl: "https://github.com/Gopi-git-bit/New-logistic-.git",
	tagFormat: "v${version}",
	plugins: [
		plugin("@semantic-release/commit-analyzer"),
		plugin("@semantic-release/release-notes-generator"),
		[
			plugin("@semantic-release/github"),
			{
				successComment: false,
				failComment: false,
				failTitle: false,
				labels: false,
				releasedLabels: false,
			},
		],
	],
};
