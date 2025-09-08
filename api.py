import requests



def get_latest_exchange_rate(_from, _to):
    
        api_key = "4093f9db26de31c3f70e7bb347f88d47"

        url = f"""http://api.exchangeratesapi.io/v1/latest?access_key={api_key}&base={_from}&symbols={_to}"""
        


        response = requests.get(url)

        rate = response.json()["rates"][_to]
        
        return rate #"{:,.2f}".format(rate)


if __name__ == "__main__":
        
        
        def count_zero_in_decimal_number(number):
                zeros = 0
                while number < 0.1:
                        number *= 10
                        zeros += 1
                return zeros
        
        rate = get_latest_exchange_rate("USD", "VND")
        
        print(rate)
        
        if rate >=1:
                rate = "{:,.7f}".format(rate)
        else:
                zeros = count_zero_in_decimal_number(rate)
                print(zeros)
                
                rate = "{:,}".format(round(rate, count_zero_in_decimal_number(rate) + 3))
                print(rate)
        
        # print(rate)
        # print("{:,.7f}".format(rate))