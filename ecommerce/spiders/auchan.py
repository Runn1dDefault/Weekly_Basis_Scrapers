import os
from datetime import datetime

import scrapy
from scrapy import Selector
from scrapy.loader import ItemLoader
from scrapy_playwright.page import PageCoroutine

from ecommerce.items import Product, remove_n
from ecommerce.settings import SCREEN_DIR


class AuchanComSpider(scrapy.Spider):
    name = 'auchan'
    allowed_domains = ['www.auchan.fr']
    custom_settings = {
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
    }
    start_urls = [
        'https://www.auchan.fr/sony-shadow-of-the-colossus-ps4/pr-C1028174',
        # 'https://www.auchan.fr/babymoov-coussin-reducteur-cosymorpho-gris/pr-C1039395'
        # 'https://www.auchan.fr/ravensburger-jeu-grand-memory-pat-patrouille/pr-C1365384',
        # 'https://www.auchan.fr/ravensburger-colle-a-puzzle-200-ml/pr-C398484',
        # 'https://www.auchan.fr/ravensburger-puzzle-3d-porcshe-911-108-pieces/pr-C1064494',
        # 'https://www.auchan.fr/ravensburger-mandala-designer-la-reine-des-neiges/pr-C869737',
        # 'https://www.auchan.fr/ravensburger-jeu-croque-carotte/pr-C396575',
        # 'https://www.auchan.fr/ravensburger-level-8/pr-4ea7bd7f-c6cc-466e-bda4-3575245c2dbf',
        # 'https://www.auchan.fr/thinkfun-rush-hour-en-edition-deluxe/pr-9448b481-48d9-429e-9d80-63c8edf17810',
        # 'https://www.auchan.fr/brio-33773-circuit-en-8-voyageurs/pr-fa501990-504a-4ab6-b2f0-6f6a7173e84b',
        # 'https://www.auchan.fr/puzzle-150-p-evoli-et-ses-evolution/pr-8bc487a5-34b6-4047-9e97-3a0a2d706bc9'
    ]
    REVIEWS_URL = 'https://www.auchan.fr/reviews?productId={}&sort=SubmissionTime:desc'

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url, self.parse,
                meta={
                    'playwright': True,
                    "playwright_include_page": True,
                    "playwright_page_coroutines": {
                        "clickallbtns": PageCoroutine(
                            "evaluate",
                            "document.querySelector('#onetrust-accept-btn-handler').click()"
                        ),
                    }
                },
                errback=self.errback
            )

    async def parse(self, response, **kwargs):
        page = response.meta["playwright_page"]
        html = await page.content()
        sel = Selector(text=html)
        loader = ItemLoader(item=Product(), selector=sel)
        loader.add_xpath('title', '//h1')
        loader.add_xpath('price', '//div[contains(@class, "product-price product-price--large")]')
        loader.add_xpath('description', '//div[contains(@class, "product-description")]/div/div')
        loader.add_xpath('breadcrumb', '//nav/span[@class="site-breadcrumb__item"]')
        loader.add_xpath('review_rate', '//span[@class="rating-value"]/span')
        loader.add_xpath('review_nb', '//span[contains(@itemprop, "reviewCount")]')
        loader.add_value('link', response.url)
        sku = self.get_sku(sel)
        loader.add_xpath('ean', sku)
        screenshot_path = os.path.join(SCREEN_DIR, f'{self.name}_{remove_n(sku)}_{int(datetime.now().timestamp())}.png')
        await page.screenshot(path=screenshot_path, full_page=True)
        loader.add_value('screenshot', screenshot_path)
        await page.close()
        yield loader.load_item()

    def get_sku(self, selector) -> str:
        for el in selector.xpath('//div[@class="product-description__feature-wrapper"]'):
            for span in el.xpath('//span/text()').getall():
                if 'EAN' in span:
                    print('found ean')
                    return (
                        el.xpath('//div[@class="product-description__feature-wrapper"]'
                                 '//div[@class="product-description__feature-values"]/text()').get()
                    ).split('/')[-1]

    async def errback(self, failure):
        page = failure.request.meta["playwright_page"]
        await page.close()


