using PricingEngine.Models;
using PricingEngine.Services;
using Xunit;

namespace PricingEngine.Tests;

public class PricingServiceTests
{
    private readonly PricingService _service = new();

    [Fact]
    public void CalculatePrice_StandardProduct_ReturnsCorrectTotal()
    {
        var request = new PriceRequest { ProductId = "EQUITY-US-100", Quantity = 10 };
        var result = _service.CalculatePrice(request);

        Assert.Equal("EQUITY-US-100", result.ProductId);
        Assert.Equal(12.50m, result.UnitPrice);
        Assert.Equal(10, result.Quantity);
        Assert.Equal(125.00m, result.Subtotal);
        Assert.Equal("standard", result.PricingTier);
    }

    [Fact]
    public void CalculatePrice_WithCoupon_AppliesDiscount()
    {
        var request = new PriceRequest
        {
            ProductId = "EQUITY-US-100",
            Quantity = 10,
            CouponCode = "INST-10"
        };
        var result = _service.CalculatePrice(request);

        Assert.True(result.Discount > 0);
        Assert.True(result.Total < result.Subtotal);
    }

    [Fact]
    public void CalculatePrice_InvalidCoupon_NoDiscount()
    {
        var request = new PriceRequest
        {
            ProductId = "EQUITY-US-100",
            Quantity = 10,
            CouponCode = "INVALID"
        };
        var result = _service.CalculatePrice(request);

        Assert.Equal(0m, result.Discount);
    }

    [Theory]
    [InlineData(1, "standard")]
    [InlineData(50, "standard")]
    [InlineData(100, "premium")]
    [InlineData(500, "premium")]
    [InlineData(1000, "professional")]
    [InlineData(5000, "professional")]
    [InlineData(10000, "institutional")]
    [InlineData(50000, "institutional")]
    public void CalculatePrice_VolumeDiscount_CorrectTier(int quantity, string expectedTier)
    {
        var request = new PriceRequest { ProductId = "DERIV-FX-OPT", Quantity = quantity };
        var result = _service.CalculatePrice(request);

        Assert.Equal(expectedTier, result.PricingTier);
    }

    [Fact]
    public void CalculatePrice_UnknownProduct_ThrowsKeyNotFound()
    {
        var request = new PriceRequest { ProductId = "INVALID-PROD", Quantity = 1 };
        Assert.Throws<KeyNotFoundException>(() => _service.CalculatePrice(request));
    }

    [Fact]
    public void CalculatePrice_ZeroQuantity_ThrowsArgument()
    {
        var request = new PriceRequest { ProductId = "EQUITY-US-100", Quantity = 0 };
        Assert.Throws<ArgumentException>(() => _service.CalculatePrice(request));
    }

    [Fact]
    public void CalculatePrice_NegativeQuantity_ThrowsArgument()
    {
        var request = new PriceRequest { ProductId = "EQUITY-US-100", Quantity = -5 };
        Assert.Throws<ArgumentException>(() => _service.CalculatePrice(request));
    }

    [Fact]
    public void CalculatePrice_TaxApplied()
    {
        var request = new PriceRequest { ProductId = "EQUITY-US-100", Quantity = 100 };
        var result = _service.CalculatePrice(request);

        Assert.True(result.Tax > 0);
        Assert.True(result.Total > result.Subtotal - result.Discount);
    }

    [Fact]
    public void CalculatePrice_CurrencyPassedThrough()
    {
        var request = new PriceRequest
        {
            ProductId = "EQUITY-EU-200",
            Quantity = 1,
            Currency = "EUR"
        };
        var result = _service.CalculatePrice(request);

        Assert.Equal("EUR", result.Currency);
    }

    [Theory]
    [InlineData("EQUITY-US-100", 12.50)]
    [InlineData("EQUITY-EU-200", 9.75)]
    [InlineData("BOND-GOV-30Y", 102.35)]
    [InlineData("BOND-CORP-5Y", 98.60)]
    [InlineData("DERIV-FX-OPT", 1.25)]
    [InlineData("DERIV-IR-SWP", 0.45)]
    [InlineData("COMM-GOLD-OZ", 2340.00)]
    [InlineData("COMM-OIL-BBL", 78.50)]
    public void CalculatePrice_AllCatalogProducts_HaveCorrectUnitPrice(string productId, decimal expectedPrice)
    {
        var request = new PriceRequest { ProductId = productId, Quantity = 1 };
        var result = _service.CalculatePrice(request);

        Assert.Equal(expectedPrice, result.UnitPrice);
    }

    [Fact]
    public void GetCatalog_ReturnsAllProducts()
    {
        var catalog = _service.GetCatalog();

        Assert.Equal(8, catalog.Count);
        Assert.Contains("EQUITY-US-100", catalog.Keys);
        Assert.Contains("COMM-GOLD-OZ", catalog.Keys);
    }
}
