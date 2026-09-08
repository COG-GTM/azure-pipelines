using PricingEngine.Models;

namespace PricingEngine.Services;

public class PricingService
{
    private static readonly Dictionary<string, decimal> Catalog = new()
    {
        ["EQUITY-US-100"] = 12.50m,
        ["EQUITY-EU-200"] = 9.75m,
        ["BOND-GOV-30Y"] = 102.35m,
        ["BOND-CORP-5Y"] = 98.60m,
        ["DERIV-FX-OPT"] = 1.25m,
        ["DERIV-IR-SWP"] = 0.45m,
        ["COMM-GOLD-OZ"] = 2340.00m,
        ["COMM-OIL-BBL"] = 78.50m,
    };

    private static readonly Dictionary<string, decimal> Coupons = new()
    {
        ["INST-10"] = 0.10m,
        ["BULK-20"] = 0.20m,
        ["PARTNER-15"] = 0.15m,
    };

    private const decimal TaxRate = 0.002m; // 20bps transaction tax

    public PriceResponse CalculatePrice(PriceRequest request)
    {
        if (!Catalog.TryGetValue(request.ProductId, out var unitPrice))
            throw new KeyNotFoundException($"Product '{request.ProductId}' not found in catalog.");

        if (request.Quantity <= 0)
            throw new ArgumentException("Quantity must be positive.", nameof(request.Quantity));

        var subtotal = unitPrice * request.Quantity;
        var discount = 0m;

        if (!string.IsNullOrEmpty(request.CouponCode) &&
            Coupons.TryGetValue(request.CouponCode, out var rate))
        {
            discount = subtotal * rate;
        }

        // Volume tier pricing
        var tier = request.Quantity switch
        {
            >= 10000 => "institutional",
            >= 1000 => "professional",
            >= 100 => "premium",
            _ => "standard"
        };

        var tierDiscount = tier switch
        {
            "institutional" => subtotal * 0.05m,
            "professional" => subtotal * 0.02m,
            "premium" => subtotal * 0.01m,
            _ => 0m
        };

        discount += tierDiscount;
        var afterDiscount = subtotal - discount;
        var tax = afterDiscount * TaxRate;

        return new PriceResponse
        {
            ProductId = request.ProductId,
            Currency = request.Currency,
            UnitPrice = unitPrice,
            Quantity = request.Quantity,
            Subtotal = subtotal,
            Discount = Math.Round(discount, 2),
            Tax = Math.Round(tax, 2),
            Total = Math.Round(afterDiscount + tax, 2),
            PricingTier = tier,
        };
    }

    public BulkPriceResponse CalculateBulkPrice(BulkPriceRequest request)
    {
        var items = request.Items.Select(CalculatePrice).ToList();
        return new BulkPriceResponse
        {
            Items = items,
            GrandTotal = items.Sum(i => i.Total),
        };
    }

    public IReadOnlyDictionary<string, decimal> GetCatalog() => Catalog;
}
