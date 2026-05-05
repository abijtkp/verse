from django.db import models



class Category(models.Model):
    category_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.category_name

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
        ordering = ['-created_at']


class Product(models.Model):
    product_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='products'
    )
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product_name

    class Meta:
        db_table = 'products'
        ordering = ['-created_at']


class Variant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants'
    )
    sku = models.CharField(max_length=100, unique=True)
    size = models.CharField(max_length=20)
    color = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def is_in_wishlist(self, user):
        if not user.is_authenticated:
            return False

        return self.wishlisted_by.filter(user=user).exists()

    def __str__(self):
        return f"{self.product.product_name} - {self.color} / {self.size}"

    class Meta:
        db_table = 'variants'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'color', 'size'],
                name='unique_color_size_per_product'
            )
        ]


class VariantImage(models.Model):
    variant = models.ForeignKey(
        Variant,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image_url = models.ImageField(upload_to='products/variants/')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.variant.product.product_name} - {self.variant.color} / {self.variant.size}"

    class Meta:
        db_table = 'variant_images'
        ordering = ['-created_at']
        
        
        
# class ProductReview(models.Model):
#     product = models.ForeignKey(
#         Product,
#         on_delete=models.CASCADE,
#         related_name='reviews'
#     )

#     user = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name='product_reviews'
#     )

#     rating = models.PositiveSmallIntegerField()
#     review_text = models.TextField(blank=True, null=True)

#     is_active = models.BooleanField(default=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'product_reviews'
#         unique_together = ('product', 'user')
#         ordering = ['-created_at']

#     def __str__(self):
#         return f"{self.product.product_name} - {self.rating} stars by {self.user.email}"        