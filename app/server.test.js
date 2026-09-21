const request = require("supertest");
const app = require("./server");

describe("API health check", () => {
  test("GET /health should return 200 and healthy status", async () => {
    const response = await request(app).get("/health");

    expect(response.statusCode).toBe(200);
    expect(response.body.status).toBe("healthy");
  });
});
