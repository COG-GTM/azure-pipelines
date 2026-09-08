using PricingEngine.Models;
using PricingEngine.Services;
using Xunit;

namespace PricingEngine.Tests;

public class BulkPricingTests
{
    private readonly PricingService _service = new();

    [Fact]
    public void CalculateBulkPrice_MultipleItems_SumsCorrectly()
    {
        var request = new BulkPriceRequest
        {
            Items = new List<PriceRequest>
            {
                new() { ProductId = "EQUITY-US-100", Quantity = 10 },
                new() { ProductId = "BOND-GOV-30Y", Quantity = 5 },
            }
        };

        var result = _service.CalculateBulkPrice(request);

        Assert.Equal(2, result.Items.Count);
        Assert.Equal(result.Items.Sum(i => i.Total), result.GrandTotal);
    }

    [Fact]
    public void CalculateBulkPrice_EmptyList_ReturnsZero()
    {
        var request = new BulkPriceRequest { Items = new List<PriceRequest>() };
        var result = _service.CalculateBulkPrice(request);

        Assert.Empty(result.Items);
        Assert.Equal(0m, result.GrandTotal);
    }

    [Fact]
    public void CalculateBulkPrice_SingleItem_MatchesSingleCalculation()
    {
        var singleRequest = new PriceRequest { ProductId = "COMM-OIL-BBL", Quantity = 100 };
        var singleResult = _service.CalculatePrice(singleRequest);

        var bulkRequest = new BulkPriceRequest
        {
            Items = new List<PriceRequest> { singleRequest }
        };
        var bulkResult = _service.CalculateBulkPrice(bulkRequest);

        Assert.Single(bulkResult.Items);
        Assert.Equal(singleResult.Total, bulkResult.Items[0].Total);
        Assert.Equal(singleResult.Total, bulkResult.GrandTotal);
    }

    [Fact]
    public void CalculateBulkPrice_InvalidProduct_Throws()
    {
        var request = new BulkPriceRequest
        {
            Items = new List<PriceRequest>
            {
                new() { ProductId = "EQUITY-US-100", Quantity = 1 },
                new() { ProductId = "NONEXISTENT", Quantity = 1 },
            }
        };

        Assert.Throws<KeyNotFoundException>(() => _service.CalculateBulkPrice(request));
    }

    [Fact]
    public void CalculateBulkPrice_WithCoupons_AppliesPerItem()
    {
        var request = new BulkPriceRequest
        {
            Items = new List<PriceRequest>
            {
                new() { ProductId = "EQUITY-US-100", Quantity = 10, CouponCode = "INST-10" },
                new() { ProductId = "BOND-GOV-30Y", Quantity = 5 },
            }
        };

        var result = _service.CalculateBulkPrice(request);

        Assert.True(result.Items[0].Discount > 0);
        Assert.Equal(0m, result.Items[1].Discount);
    }

    [Fact]
    public void CalculateBulkPrice_LargeOrder_InstitutionalTier()
    {
        var request = new BulkPriceRequest
        {
            Items = new List<PriceRequest>
            {
                new() { ProductId = "DERIV-FX-OPT", Quantity = 50000 },
                new() { ProductId = "DERIV-IR-SWP", Quantity = 25000 },
            }
        };

        var result = _service.CalculateBulkPrice(request);

        Assert.All(result.Items, item => Assert.Equal("institutional", item.PricingTier));
    }
}
