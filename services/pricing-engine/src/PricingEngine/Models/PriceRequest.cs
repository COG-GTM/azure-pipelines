namespace PricingEngine.Models;

public class PriceRequest
{
    public string ProductId { get; set; } = string.Empty;
    public string Currency { get; set; } = "USD";
    public int Quantity { get; set; } = 1;
    public string? CouponCode { get; set; }
}

public class PriceResponse
{
    public string ProductId { get; set; } = string.Empty;
    public string Currency { get; set; } = "USD";
    public decimal UnitPrice { get; set; }
    public int Quantity { get; set; }
    public decimal Subtotal { get; set; }
    public decimal Discount { get; set; }
    public decimal Tax { get; set; }
    public decimal Total { get; set; }
    public string PricingTier { get; set; } = "standard";
}

public class BulkPriceRequest
{
    public List<PriceRequest> Items { get; set; } = new();
}

public class BulkPriceResponse
{
    public List<PriceResponse> Items { get; set; } = new();
    public decimal GrandTotal { get; set; }
}
