"""Fungible Assets - FA12

Copyright (c) 2025 - present Trilitech Limited
Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Inspired by https://gitlab.com/tezos/tzip/-/blob/master/proposals/tzip-7/tzip-7.md
"""


import smartpy as sp


@sp.module
def m():
    class AdminInterface(sp.Contract):
        @sp.private(with_storage="read-only")
        def is_administrator_(self, sender):
            sp.cast(sp.sender, sp.address)
            """Not standard, may be re-defined through inheritance."""
            return True

    class CommonInterface(AdminInterface):
        def __init__(self):
            AdminInterface.__init__(self)
            self.data.ledger = sp.cast(
                sp.big_map(),
                sp.big_map[
                    sp.address,
                    sp.record(approvals=sp.map[sp.address, sp.nat], balance=sp.nat),
                ],
            )
            self.data.total_supply = 0
            self.data.token_metadata = sp.cast(
                sp.big_map(),
                sp.big_map[
                    sp.nat,
                    sp.record(token_id=sp.nat, token_info=sp.map[sp.string, sp.bytes]),
                ],
            )
            self.data.metadata = sp.cast(
                sp.big_map(),
                sp.big_map[sp.string, sp.bytes],
            )

        @sp.private(with_storage="read-only")
        def is_paused_(self):
            """Not standard, may be re-defined through inheritance."""
            return False

    class Fa1_2(CommonInterface):
        def __init__(self, metadata, ledger, token_metadata):
            """
            token_metadata spec: https://gitlab.com/tzip/tzip/-/blob/master/proposals/tzip-12/tzip-12.md#token-metadata
            Token-specific metadata is stored/presented as a Michelson value of type (map string bytes).
            A few of the keys are reserved and predefined:

            - ""          : Should correspond to a TZIP-016 URI which points to a JSON representation of the token metadata.
            - "name"      : Should be a UTF-8 string giving a “display name” to the token.
            - "symbol"    : Should be a UTF-8 string for the short identifier of the token (e.g. XTZ, EUR, …).
            - "decimals"  : Should be an integer (converted to a UTF-8 string in decimal)
                which defines the position of the decimal point in token ledger for display purposes.

            contract_metadata spec: https://gitlab.com/tzip/tzip/-/blob/master/proposals/tzip-16/tzip-16.md
            """
            CommonInterface.__init__(self)
            self.data.metadata = metadata
            self.data.token_metadata = sp.big_map(
                {0: sp.record(token_id=0, token_info=token_metadata)}
            )

            for owner in ledger.items():
                self.data.ledger[owner.key] = owner.value
                self.data.total_supply += owner.value.balance

        @sp.entrypoint
        def transfer(self, param):
            sp.cast(
                param,
                sp.record(from_=sp.address, to_=sp.address, value=sp.nat).layout(
                    ("from_ as from", ("to_ as to", "value"))
                ),
            )
            balance_from = self.data.ledger.get(
                param.from_, default=sp.record(balance=0, approvals={})
            )
            balance_to = self.data.ledger.get(
                param.to_, default=sp.record(balance=0, approvals={})
            )
            balance_from.balance = sp.as_nat(
                balance_from.balance - param.value, error="FA1.2_InsufficientBalance"
            )
            balance_to.balance += param.value
            if not self.is_administrator_(sp.sender):
                assert not self.is_paused_(), "FA1.2_Paused"
                if param.from_ != sp.sender:
                    balance_from.approvals[sp.sender] = sp.as_nat(
                        balance_from.approvals[sp.sender] - param.value,
                        error="FA1.2_NotAllowed",
                    )
            self.data.ledger[param.from_] = balance_from
            self.data.ledger[param.to_] = balance_to

        @sp.entrypoint
        def approve(self, param):
            sp.cast(
                param,
                sp.record(spender=sp.address, value=sp.nat).layout(
                    ("spender", "value")
                ),
            )
            assert not self.is_paused_(), "FA1.2_Paused"
            spender_balance = self.data.ledger.get(
                sp.sender, default=sp.record(balance=0, approvals={})
            )
            alreadyApproved = spender_balance.approvals.get(param.spender, default=0)
            assert (
                alreadyApproved == 0 or param.value == 0
            ), "FA1.2_UnsafeAllowanceChange"
            spender_balance.approvals[param.spender] = param.value
            self.data.ledger[sp.sender] = spender_balance

        @sp.entrypoint
        def getBalance(self, param):
            (address, callback) = param
            result = self.data.ledger.get(
                address, default=sp.record(balance=0, approvals={})
            ).balance
            sp.transfer(result, sp.tez(0), callback)

        @sp.entrypoint
        def getAllowance(self, param):
            (args, callback) = param
            result = self.data.ledger.get(
                args.owner, default=sp.record(balance=0, approvals={})
            ).approvals.get(args.spender, default=0)
            sp.transfer(result, sp.tez(0), callback)

        @sp.entrypoint
        def getTotalSupply(self, param: sp.pair[sp.unit, sp.contract[sp.nat]]):
            sp.transfer(self.data.total_supply, sp.tez(0), sp.snd(param))

        @sp.offchain_view()
        def token_metadata(self, token_id):
            """Return the token-metadata URI for the given token. (token_id must be 0)."""
            sp.cast(token_id, sp.nat)
            return self.data.token_metadata[token_id]

    ##########
    # Mixins #
    ##########

    class Admin(sp.Contract):
        def __init__(self, administrator):
            self.data.administrator = administrator

        @sp.private(with_storage="read-only")
        def is_administrator_(self, sender):
            return sender == self.data.administrator

        @sp.entrypoint
        def setAdministrator(self, params: sp.address):
            assert self.is_administrator_(sp.sender), "Fa1.2_NotAdmin"
            self.data.administrator = params

        @sp.entrypoint()
        def getAdministrator(self, param: sp.pair[sp.unit, sp.contract[sp.address]]):
            sp.transfer(self.data.administrator, sp.tez(0), sp.snd(param))

        @sp.onchain_view()
        def get_administrator(self):
            return self.data.administrator

    class Pause(AdminInterface):
        def __init__(self):
            AdminInterface.__init__(self)
            self.data.paused = False

        @sp.private(with_storage="read-only")
        def is_paused_(self):
            return self.data.paused

        @sp.entrypoint
        def setPause(self, param):
            sp.cast(param, sp.bool)
            assert self.is_administrator_(sp.sender), "Fa1.2_NotAdmin"
            self.data.paused = param

    class Mint(CommonInterface):
        def __init__(self):
            CommonInterface.__init__(self)

        @sp.entrypoint
        def mint(self, param: sp.record(address=sp.address, value=sp.nat)):
            assert self.is_administrator_(sp.sender), "Fa1.2_NotAdmin"
            receiver_balance = self.data.ledger.get(
                param.address, default=sp.record(balance=0, approvals={})
            )
            receiver_balance.balance += param.value
            self.data.ledger[param.address] = receiver_balance
            self.data.total_supply += param.value

    class Burn(CommonInterface):
        def __init__(self):
            CommonInterface.__init__(self)

        @sp.entrypoint
        def burn(self, param: sp.record(address=sp.address, value=sp.nat)):
            assert self.is_administrator_(sp.sender), "Fa1.2_NotAdmin"
            receiver_balance = self.data.ledger.get(
                param.address, default=sp.record(balance=0, approvals={})
            )
            receiver_balance.balance = sp.as_nat(
                receiver_balance.balance - param.value,
                error="FA1.2_InsufficientBalance",
            )
            self.data.ledger[param.address] = receiver_balance
            self.data.total_supply = sp.as_nat(self.data.total_supply - param.value)

    class ChangeMetadata(CommonInterface):
        def __init__(self):
            CommonInterface.__init__(self)

        @sp.entrypoint
        def update_metadata(self, key, value):
            """An entrypoint to allow the contract metadata to be updated."""
            assert self.is_administrator_(sp.sender), "Fa1.2_NotAdmin"
            self.data.metadata[key] = value

    ##########
    # Tests #
    ##########

    class Fa1_2TestFull(Admin, Pause, Fa1_2, Mint, Burn, ChangeMetadata):
        def __init__(self, administrator, metadata, ledger, token_metadata):
            ChangeMetadata.__init__(self)
            Burn.__init__(self)
            Mint.__init__(self)
            Fa1_2.__init__(self, metadata, ledger, token_metadata)
            Pause.__init__(self)
            Admin.__init__(self, administrator)

    class Viewer_nat(sp.Contract):
        def __init__(self):
            self.data.last = sp.cast(None, sp.option[sp.nat])

        @sp.entrypoint
        def target(self, params):
            self.data.last = sp.Some(params)

    class Viewer_address(sp.Contract):
        def __init__(self):
            self.data.last = sp.cast(None, sp.option[sp.address])

        @sp.entrypoint
        def target(self, params):
            self.data.last = sp.Some(params)


if "main" in __name__:

    @sp.add_test()
    def test():
        sc = sp.test_scenario("FA12")
        sc.h1("FA1.2 template - Fungible assets")

        # sp.test_account generates ED25519 key-pairs deterministically:
        admin = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob = sp.test_account("Robert")

        # Let's display the accounts:
        sc.h1("Accounts")
        sc.show([admin, alice, bob])

        sc.h1("Contract")
        token_metadata = {
            "decimals": sp.scenario_utils.bytes_of_string(
                "18"
            ),  # Mandatory by the spec
            "name": sp.scenario_utils.bytes_of_string("My Great Token"),  # Recommended
            "symbol": sp.scenario_utils.bytes_of_string("MGT"),  # Recommended
            # Extra fields
            "icon": sp.scenario_utils.bytes_of_string(
                "https://smartpy.io/static/img/logo-only.svg"
            ),
        }
        # We initialize with an empty metadata at this stage
        c1 = m.Fa1_2TestFull(
            administrator=admin.address,
            metadata=sp.big_map(),
            token_metadata=token_metadata,
            ledger={},
        )

        # Now that we instantiated the contract metadata,
        # we can build the metadata content:
        contract_metadata_content = sp.create_tzip16_metadata(
            name="SmartPy FA1.2 Token Template",
            description="Example template for an FA1.2 contract from SmartPy.",
            version="1.0.0",
            license_name="CC-BY-SA",
            license_details="Creative Commons Attribution Share Alike license 4.0 https://creativecommons.org/licenses/by/4.0/",
            interfaces=["TZIP-007", "TZIP-016"],
            authors=["SmartPy <https://smartpy.io/#contact>"],
            homepage="https://smartpy.io/ide?template=fa1_2.py",
            # Optionally, upload the source code to IPFS and add the URI here
            source_uri=None,
            offchain_views=c1.get_offchain_views(),
        )

        # The content can then be uploaded to IPFS as a JSON file using
        # metadata_uri = sp.pin_on_ipfs(contract_metadata_content, api_key=None, secret_key=None)
        # Or with any other service.
        # `json.dumps(contract_metadata_content)` provide the content.

        # After uploading the metadata to IPFS, we can set its URI in the contract.
        # Replace it by your IPFS URI.
        metadata_uri = "ipfs://QmQ7qNiLrUCTxDhRj9PqggDsyBU4VUbHX2wf2iafqXd2o6"

        c1.data.metadata = sp.scenario_utils.metadata_of_url(metadata_uri)

        # Originate the contract in the test scenario.
        sc += c1

        if sc.simulation_mode() is sp.SimulationMode.MOCKUP:
            sc.p("mockups - TODO off chain views")
            return

        sc.h1("Offchain view - token_metadata")
        sc.verify_equal(
            sp.View(c1, "token_metadata")(0),
            sp.record(
                token_id=0,
                token_info=sp.map(
                    {
                        "decimals": sp.scenario_utils.bytes_of_string("18"),
                        "name": sp.scenario_utils.bytes_of_string("My Great Token"),
                        "symbol": sp.scenario_utils.bytes_of_string("MGT"),
                        "icon": sp.scenario_utils.bytes_of_string(
                            "https://smartpy.io/static/img/logo-only.svg"
                        ),
                    }
                ),
            ),
        )

        sc.h1("Attempt to update metadata")
        sc.verify(
            c1.data.metadata[""]
            == sp.scenario_utils.bytes_of_string(
                "ipfs://QmQ7qNiLrUCTxDhRj9PqggDsyBU4VUbHX2wf2iafqXd2o6"
            )
        )
        c1.update_metadata(key="", value=sp.bytes("0x00"), _sender=admin)
        sc.verify(c1.data.metadata[""] == sp.bytes("0x00"))

        sc.h1("Entrypoints")
        sc.h2("Admin mints a few coins")
        c1.mint(address=alice.address, value=12, _sender=admin)
        c1.mint(address=alice.address, value=3, _sender=admin)
        c1.mint(address=alice.address, value=3, _sender=admin)
        sc.h2("Alice transfers to Bob")
        c1.transfer(from_=alice.address, to_=bob.address, value=4, _sender=alice)
        sc.verify(c1.data.ledger[alice.address].balance == 14)
        sc.h2("Bob tries to transfer from Alice but he doesn't have her approval")
        c1.transfer(
            from_=alice.address, to_=bob.address, value=4, _sender=bob, _valid=False
        )
        sc.h2("Alice approves Bob and Bob transfers")
        c1.approve(spender=bob.address, value=5, _sender=alice)
        c1.transfer(from_=alice.address, to_=bob.address, value=4, _sender=bob)
        sc.h2("Bob tries to over-transfer from Alice")
        c1.transfer(
            from_=alice.address, to_=bob.address, value=4, _sender=bob, _valid=False
        )
        sc.h2("Admin burns Bob token")
        c1.burn(address=bob.address, value=1, _sender=admin)
        sc.verify(c1.data.ledger[alice.address].balance == 10)
        sc.h2("Alice tries to burn Bob token")
        c1.burn(address=bob.address, value=1, _sender=alice, _valid=False)
        sc.h2("Admin pauses the contract and Alice cannot transfer anymore")
        c1.setPause(True, _sender=admin)
        c1.transfer(
            from_=alice.address, to_=bob.address, value=4, _sender=alice, _valid=False
        )
        sc.verify(c1.data.ledger[alice.address].balance == 10)
        sc.h2("Admin transfers while on pause")
        c1.transfer(from_=alice.address, to_=bob.address, value=1, _sender=admin)
        sc.h2("Admin unpauses the contract and transfers are allowed")
        c1.setPause(False, _sender=admin)
        sc.verify(c1.data.ledger[alice.address].balance == 9)
        c1.transfer(from_=alice.address, to_=bob.address, value=1, _sender=alice)

        sc.verify(c1.data.total_supply == 17)
        sc.verify(c1.data.ledger[alice.address].balance == 8)
        sc.verify(c1.data.ledger[bob.address].balance == 9)

        sc.h1("Views")
        sc.h2("Balance")
        view_balance = m.Viewer_nat()
        sc += view_balance
        target = sp.contract(sp.nat, view_balance.address, "target").unwrap_some()
        c1.getBalance((alice.address, target))
        sc.verify_equal(view_balance.data.last, sp.Some(8))

        sc.h2("Administrator")
        view_administrator = m.Viewer_address()
        sc += view_administrator
        target = sp.contract(
            sp.address, view_administrator.address, "target"
        ).unwrap_some()
        c1.getAdministrator((sp.unit, target))
        sc.verify_equal(view_administrator.data.last, sp.Some(admin.address))

        sc.h2("Total Supply")
        view_totalSupply = m.Viewer_nat()
        sc += view_totalSupply
        target = sp.contract(sp.nat, view_totalSupply.address, "target").unwrap_some()
        c1.getTotalSupply((sp.unit, target))
        sc.verify_equal(view_totalSupply.data.last, sp.Some(17))

        sc.h2("Allowance")
        view_allowance = m.Viewer_nat()
        sc += view_allowance
        target = sp.contract(sp.nat, view_allowance.address, "target").unwrap_some()
        c1.getAllowance((sp.record(owner=alice.address, spender=bob.address), target))
        sc.verify_equal(view_allowance.data.last, sp.Some(1))
