package com.itzkarlo.olympus.minecraft;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class ObservationDifferTest {
    private static ObservationDiffer.Facts facts(float health) {
        return new ObservationDiffer.Facts(
            true, "multiplayer", "Hermes SMP", "overworld", health, 20
        );
    }

    @Test
    void healthChangesProduceDamageHealingAndOneDeath() {
        ObservationDiffer differ = new ObservationDiffer();
        assertTrue(differ.update(facts(20)).isEmpty());
        List<ObservationDiffer.Event> damage = differ.update(facts(17));
        assertEquals("player.damage_taken", damage.getFirst().type());
        assertEquals(3, damage.getFirst().payload().get("amount").getAsFloat());
        assertEquals("player.healed", differ.update(facts(18)).getFirst().type());

        List<ObservationDiffer.Event> death = differ.update(facts(0));
        assertEquals(2, death.size());
        assertEquals("player.died", death.get(1).type());
        assertTrue(differ.update(facts(0)).isEmpty());
    }

    @Test
    void dimensionAndSessionEdgesAreExplicit() {
        ObservationDiffer differ = new ObservationDiffer();
        differ.update(facts(20));
        ObservationDiffer.Facts nether = new ObservationDiffer.Facts(
            true, "multiplayer", "Hermes SMP", "nether", 20, 20
        );
        assertEquals("dimension.changed", differ.update(nether).getFirst().type());
        ObservationDiffer.Facts left = new ObservationDiffer.Facts(
            false, "multiplayer", "Hermes SMP", null, 0, 0
        );
        assertEquals("session.left", differ.update(left).getFirst().type());
    }
}
