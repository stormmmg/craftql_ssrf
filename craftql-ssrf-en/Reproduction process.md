1.Install Craft CMS 3.x and register an account.

2.Install the CraftQL plugin and enable it.

![image-20260207104103767](https://github.com/stormmmg/craftql_ssrf/blob/master/images/image-20260207104103767.png)

3.Configure tokens in the plugin configuration interface.

![image-20260207104232955](https://github.com/stormmmg/craftql_ssrf/blob/master/images/image-20260207104232955.png)

4.Perform configuration in the tokens interface and turn on mutations. (If the vulnerability reproduction fails, try enabling the options in query fields.)

![image-20260207114232573](https://github.com/stormmmg/craftql_ssrf/blob/master/images/image-20260207114232573.png)

5.Execute the POC (Proof of Concept) to verify the vulnerability.

![image-20260207114436071](https://github.com/stormmmg/craftql_ssrf/blob/master/images/image-20260207114436071.png)

It can be seen that the /etc/passwd file is retrieved, confirming the existence of the vulnerability.
