using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Mvc.Testing;
using PricingEngine.Models;
using Xunit;

namespace PricingEngine.Tests;

public class PricingControllerTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public PricingControllerTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task GetCatalog_ReturnsOk()
    {
        var response = await _client.GetAsync("/api/pricing/catalog");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task Health_ReturnsOk()
    {
        var response = await _client.GetAsync("/api/pricing/health");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task CalculatePrice_ValidRequest_ReturnsOk()
    {
        var request = new PriceRequest { ProductId = "EQUITY-US-100", Quantity = 10 };
        var response = await _client.PostAsJsonAsync("/api/pricing/calculate", request);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var result = await response.Content.ReadFromJsonAsync<PriceResponse>();
        Assert.NotNull(result);
        Assert.Equal("EQUITY-US-100", result.ProductId);
    }

    [Fact]
    public async Task CalculatePrice_UnknownProduct_ReturnsNotFound()
    {
        var request = new PriceRequest { ProductId = "DOES-NOT-EXIST", Quantity = 1 };
        var response = await _client.PostAsJsonAsync("/api/pricing/calculate", request);

        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }

    [Fact]
    public async Task BulkPrice_ValidRequest_ReturnsOk()
    {
        var request = new BulkPriceRequest
        {
            Items = new List<PriceRequest>
            {
                new() { ProductId = "EQUITY-US-100", Quantity = 5 },
                new() { ProductId = "BOND-GOV-30Y", Quantity = 2 },
            }
        };
        var response = await _client.PostAsJsonAsync("/api/pricing/bulk", request);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var result = await response.Content.ReadFromJsonAsync<BulkPriceResponse>();
        Assert.NotNull(result);
        Assert.Equal(2, result.Items.Count);
    }
}
