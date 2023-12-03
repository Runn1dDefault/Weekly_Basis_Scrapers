import os
import time
from datetime import datetime
from typing import List, Dict, Any, Union
from urllib.parse import urlparse

import scrapy
from scrapy.loader import ItemLoader
from selenium import webdriver
from selenium.webdriver.common.by import By

from ecommerce.items import Product
from ecommerce.settings import SCREEN_DIR, CHROME_DRIVER_PATH


class ELeclercSpider(scrapy.Spider):
    name = 'e-leclerc'
    start_urls = [
        'https://www.e.leclerc/fp/gravitrax-bloc-d-action-zipline-tyrolienne-4005556261581',
        # 'https://www.e.leclerc/fp/tiptoi-mini-doc-les-dinosaures-4005556000289',
        # 'https://www.e.leclerc/fp/grand-memory-pat-patrouille-paw-paw-patrol-core-4005556207435',
        # 'https://www.e.leclerc/fp/escape-puzzle-kids-mission-spatiale-368-pieces-4005556132676',
        # 'https://www.e.leclerc/fp/colle-a-puzzle-200-ml-4005556179541',
        # 'https://www.e.leclerc/fp/puzzle-3d-porsche-911-r-porsche-911-r-4005556125289',
        # 'https://www.e.leclerc/fp/mandala-midi-disney-la-reine-des-neiges-2-dfz2-disney-frozen-2-4005556290260',
        # 'https://www.e.leclerc/fp/looky-sketch-book-robes-de-soiree-4005556180820',
        # 'https://www.e.leclerc/fp/croque-carotte-4005556222230',
        # 'https://www.e.leclerc/fp/rush-hour-en-edition-deluxe-4005556764389',
        # 'https://www.e.leclerc/fp/33773-circuit-en-8-voyageurs-7312350337730',
        # 'https://www.e.leclerc/fp/nathan-puzzle-pokemon-evoli-et-ses-evolutions-150-pieces-4005556860302',
        # 'https://www.e.leclerc/fp/puzzle-1000-p-cerf-fantastique-4005556150182'
    ]
    custom_settings = {
        "DOWNLOAD_DELAY": 0.25
    }
    PRODUCT_DETAIL_BY_SKU = 'https://www.e.leclerc/api/rest/live-api/product-details-by-sku/{}'
    REVIEWS_BY_PRODUCT_SKU = 'https://www.e.leclerc/api/rest/bazaarvoice-api/reviews?productId={}' \
                             '&sortKey=TotalPositiveFeedbackCount&sortOrder=Desc'
    CATEGORIES_DETAIL = 'https://www.e.leclerc/api/rest/live-api/category-details-by-codes?codes={}'

    def start_requests(self):
        for url in self.start_urls:
            sku = urlparse(url).path.split('-')[-1]
            detail_url = self.PRODUCT_DETAIL_BY_SKU.format(sku)
            yield scrapy.Request(detail_url, self.parse, meta={'sku': sku, 'url': url})

    def parse(self, response, **kwargs):
        data = response.json()
        loader = ItemLoader(item=Product(), response=response)
        sku, url = data.get('sku') or response.meta['sku'], response.meta['url']
        loader.add_value('link', url)
        loader.add_value('ean', sku)
        loader.add_value('title', data['label'])
        detail = data['variants'][0]
        attributes = detail['attributes']
        loader.add_value('description', [i['value'] for i in attributes if i['label'].lower() == 'description'])
        price = self.get_price(detail)
        if price is None:
            self.logger.debug('Not found price for url: %s' % url)
            return
        loader.add_value('price', price)
        yield from self.categories_filter(loader, data['categories'], sku, url)

    @staticmethod
    def get_price(detail: Dict[str, Any]) -> Union[str, None]:
        price_data = None
        for i in detail['offers']:
            if not i['isDefault']:
                continue
            price_data = i['basePrice']
            break
        if price_data is None:
            return
        discount_price = price_data.get('discountPrice')
        price = str(int(discount_price['totalPrice']['price'] if discount_price else price_data['price']['price']))
        counter = len(price) // 2
        if counter == 1:
            counter = 2
        return str(int(price) / int(f'1{"".join(["0" for _ in range(counter)])}'))

    def categories_filter(self, loader: ItemLoader, categories: List[Dict[str, Any]], product_id: str, url: str):
        code, max_level_num = None, 0
        for category_data in categories:
            pass_c = False
            for attr in category_data['attributes']:
                page_deleted = attr['code'] == 'page-deleted' and attr['value'].get('page-deleted')
                is_not_navigation = attr['code'] == 'page-type' and attr['value'].get('text') != 'NAVIGATION'
                page_hidden = attr['code'] == 'page-hidden' and attr['value'].get('boolean')
                if page_hidden or is_not_navigation or page_deleted:
                    pass_c = True
                    break
                level_num = attr['value'].get('number', 0)
                if attr['code'] == 'page-level' and level_num > max_level_num:
                    max_level_num = level_num
                    code = category_data['code']
                    break
            if pass_c:
                continue
        if code is None:
            return
        yield scrapy.Request(
            self.CATEGORIES_DETAIL.format(code),
            self.parse_breadcrumb,
            meta={'loader': loader, 'sku': product_id, 'url': url}
        )

    def parse_breadcrumb(self, response):
        data = response.json()
        if not data:
            return
        loader = response.meta['loader']
        loader.add_value(
            'breadcrumb', [i['label'] if i['label'] != 'root' else 'Accueil' for i in data[0]['breadcrumb']]
        )
        yield scrapy.Request(
            self.REVIEWS_BY_PRODUCT_SKU.format(response.meta['sku']),
            self.parse_reviews,
            meta=response.meta
        )

    def parse_reviews(self, response):
        data = response.json()
        loader = response.meta['loader']

        if data and data.get('includes') and data['includes'].get('productsOrder'):
            data = data['includes']['products'][0]
            loader.add_value('review_rate', str(data['reviewStatistics']['averageOverallRating']))
            loader.add_value('review_nb', str(data['reviewStatistics']['totalReviewCount']))
        self.save_screem(loader, response.meta['url'], response.meta['sku'])
        yield loader.load_item()

    def save_screem(self, loader: ItemLoader, url: str, sku: str) -> None:
        screenshot_path = os.path.join(SCREEN_DIR, f'{self.name}_{sku}_{int(datetime.now().timestamp())}.png')
        options = webdriver.ChromeOptions()
        options.headless = True
        driver = webdriver.Chrome(executable_path=CHROME_DRIVER_PATH, options=options)
        driver.get(url)
        time.sleep(3)
        driver.find_element(By.ID, 'onetrust-accept-btn-handler').click()
        time.sleep(1)
        scroll_func = lambda X: driver.execute_script('return document.body.parentNode.scroll' + X)
        driver.set_window_size(1000, scroll_func('Height'))  # May need manual adjustment
        driver.find_element(By.XPATH, '//body').screenshot(screenshot_path)
        driver.quit()
        loader.add_value('screenshot', screenshot_path)
