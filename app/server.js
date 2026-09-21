const express = require("express");

const app = express();
const PORT = process.env.PORT || 3000;

app.get("/", (req, res) => {
  res.json({
    message: "Local DevOps Project",
    version: process.env.APP_VERSION || "v1",
    environment: process.env.ENVIRONMENT || "dev"
  });
});

app.get("/health", (req, res) => {
  res.status(200).json({ status: "healthy" });
});

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
  });
}

module.exports = app;