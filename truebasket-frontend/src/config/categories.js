import { Coffee, Cookie, CupSoda, Croissant, Milk, Nut, Popcorn, Soup, Wheat, Candy, Salad, Egg } from "lucide-react";

/** Browse tiles. `q` is the search phrase sent to Open Food Facts. */
export const CATEGORIES = [
  { q: "Muesli", label: "Muesli & granola", sub: "Oats, nuts, fruit", icon: Wheat, tint: "#f3e6c4", ink: "#8a5a12" },
  { q: "Breakfast cereal", label: "Breakfast cereals", sub: "Flakes, chocos, loops", icon: Croissant, tint: "#f6dccb", ink: "#9b3d2b" },
  { q: "Oats", label: "Oats", sub: "Rolled, instant, masala", icon: Wheat, tint: "#e6ecd6", ink: "#3f6b35" },
  { q: "Biscuits", label: "Biscuits & cookies", sub: "Glucose, cream, digestive", icon: Cookie, tint: "#f1e0c8", ink: "#8a5a12" },
  { q: "Instant noodles", label: "Noodles & pasta", sub: "Instant, atta, cup", icon: Soup, tint: "#f8e3b5", ink: "#9a6a12" },
  { q: "Chips", label: "Chips & namkeen", sub: "Salty snacks", icon: Popcorn, tint: "#f8dcc0", ink: "#9b3d2b" },
  { q: "Chocolate", label: "Chocolates & sweets", sub: "Bars, candies", icon: Candy, tint: "#ecd6cf", ink: "#7a3b2b" },
  { q: "Peanut butter", label: "Spreads", sub: "Peanut butter, jams", icon: Nut, tint: "#efdcc2", ink: "#8a5a12" },
  { q: "Milk", label: "Dairy", sub: "Milk, curd, paneer", icon: Milk, tint: "#e3eef1", ink: "#1b655d" },
  { q: "Juice", label: "Beverages", sub: "Juices, soft drinks", icon: CupSoda, tint: "#dcebe0", ink: "#3f6b35" },
  { q: "Tea", label: "Tea & coffee", sub: "Leaf, instant, green", icon: Coffee, tint: "#e8ddd3", ink: "#5b3b26" },
  { q: "Ketchup", label: "Sauces & spreads", sub: "Ketchup, chutneys", icon: Salad, tint: "#f2d9d2", ink: "#9b3d2b" },
  { q: "Atta", label: "Atta & flours", sub: "Wheat, multigrain", icon: Wheat, tint: "#efe6d2", ink: "#6b5a2b" },
  { q: "Protein bar", label: "Protein & bars", sub: "Bars, powders", icon: Egg, tint: "#e2ecea", ink: "#1b655d" },
];
