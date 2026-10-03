-- show tables from ecommerce

SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';

-- use the ecommerce database
USE ecommerce;

-- top 10 rows from each table

SELECT * FROM public.carts LIMIT 30;

SELECT * FROM product_variants 
WHERE id = 1325 LIMIT 30;

SELECT * FROM ecommerce.public.product_variants 
WHERE product_id = 85 LIMIT 30;

SELECT * FROM ecommerce.public.products 
-- WHERE id = 85 
LIMIT 30;
-- product: 85, --> variant 1325
-- FROM information_schema.columns WHERE table_name = 'carts';

