; Copyright (c) 2017-present Walmart, Inc.
;
; Licensed under the Apache License, Version 2.0 (the "License")
; you may not use this file except in compliance with the License.
; You may obtain a copy of the License at
;
;     http://www.apache.org/licenses/LICENSE-2.0
;
; Unless required by applicable law or agreed to in writing, software
; distributed under the License is distributed on an "AS IS" BASIS,
; WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
; See the License for the specific language governing permissions and
; limitations under the License.

(ns com.walmartlabs.lacinia.interfaces-test
  (:require [clojure.test :refer [deftest is testing]]
            [com.walmartlabs.lacinia :refer [execute]]
            [com.walmartlabs.lacinia.schema :as schema]
            [com.walmartlabs.test-utils :refer [expect-exception]]))

(def starship-data
  (->> [{:id "001"
         :name "Millennium Falcon"
         :length 34.37
         :class "Light freighter"
         ::type :starship}
        {:id "002"
         :name "X-wing"
         :length 12.5
         :class "Starfighter"
         ::type :starship}
        {:id "003"
         :name "Executor"
         :length 19000
         :class "Star dreadnought"
         ::type :starship}
        {:id "004"
         :name "Death Star"
         :length 120000
         :class "Deep Space Mobile Battlestation"
         ::type :starship}]
       (map (juxt :id identity))
       (into {})))

(defn ^:private get-starship
  [id]
  (get starship-data id))

(def ^:private test-schema
  {:enums
   {:unit {:values [:METER :FOOT]}}

   :interfaces
   {:vehicle {:fields {:id {:type '(non-null String)}
                       :name {:type '(non-null String)}
                       :length {:type 'Float
                                :args {:unit {:type :unit}}}
                       :class {:type 'String}}}}
   :objects
   {:starship
    {:implements [:vehicle]
     :fields {:id {:type '(non-null String)}
              :name {:type '(non-null String)}
              :length {:type 'Float
                       :args {:unit {:type :unit
                                     :default-value :METER}}
                       :resolve (fn [ctx args v]
                                  (let [{:keys [unit]} args
                                        length (:length v)]
                                    (if-not (= unit :METER)
                                      (when length
                                        (* length 3.28))
                                      length)))}
              :class {:type 'String}}}}

   :queries
   {:starship
    {:type :starship
     :args {:id {:type '(non-null String)}}
     :resolve (fn [ctx args v]
                (let [{:keys [id]} args]
                  (get-starship id)))}}})

(deftest compatible-arguments
  (testing "field argument is optional and had default value"
    (let [compiled-schema (schema/compile test-schema {:default-field-resolver schema/hyphenating-default-field-resolver})
          q1 "query FetchStarship {
                 starship(id: \"001\") {
                    name
                    class
                    length(unit: FOOT)
                 }
              }"
          q2 "query FetchStarship {
                starship(id: \"001\") {
                   name
                   class
                   length
                }
             }"]
      (is (= {:data {:starship {:name "Millennium Falcon"
                                :class "Light freighter"
                                :length 112.73359999999998}}}
             (execute compiled-schema q1 nil nil))
          "schema should compile and query is successful")
      (is (= {:data {:starship {:name "Millennium Falcon"
                                :class "Light freighter"
                                :length 34.37}}}
             (execute compiled-schema q2 nil nil))
          "schema should compile and query is successful")))

  (testing "field argument is required by the interface and not present in the object"
    (let [invalid-schema (-> test-schema
                             (assoc-in [:interfaces :vehicle :fields :length :args :unit :type]
                                       '(non-null :unit))
                             (assoc-in [:objects :speeder]
                                       {:implements [:vehicle]
                                        :fields {:id {:type '(non-null String)}
                                                 :name {:type '(non-null String)}
                                                 ;; :length field is missing argument :unit
                                                 :length {:type 'Float}
                                                 :class {:type 'String}}}))]
      (expect-exception
        "Missing interface field argument in object definition."
        {:field-name :speeder/length
         :interface-argument :vehicle/length.unit}
        (schema/compile invalid-schema {:default-field-resolver schema/hyphenating-default-field-resolver}))))

  (testing "field argument is not required by the interface and is not present in the object"
    (let [invalid-schema (-> test-schema
                             (assoc-in [:interfaces :vehicle :fields :length :args :unit :type] :unit)
                             (assoc-in [:objects :speeder]
                                       {:implements [:vehicle]
                                        :fields {:id {:type '(non-null String)}
                                                 :name {:type '(non-null String)}
                                                 ;; :length field is missing argument :unit
                                                 :length {:type 'Float}
                                                 :class {:type 'String}}}))]
      (expect-exception
        "Missing interface field argument in object definition."
        {:field-name :speeder/length
         :interface-argument :vehicle/length.unit}
        (schema/compile invalid-schema {:default-field-resolver schema/hyphenating-default-field-resolver}))))

  (testing "field argument in the interface has a different type to field argument in the object"
    (let [invalid-schema (-> test-schema
                             (assoc-in [:objects :speeder]
                                       {:implements [:vehicle]
                                        :fields {:id {:type '(non-null String)}
                                                 :name {:type '(non-null String)}
                                                 :length {:type 'Float
                                                          ;; invalid type of :unit arg
                                                          :args {:unit {:type 'String}}}
                                                 :class {:type 'String}}}))]
      (expect-exception
        "Object field's argument is not compatible with extended interface's argument type."
        {:argument-name :speeder/length.unit
         :interface-name :vehicle}
        (schema/compile invalid-schema {:default-field-resolver schema/hyphenating-default-field-resolver})))

    (let [invalid-schema (-> test-schema
                             (assoc-in [:interfaces :vehicle :fields :length :args :unit :type]
                                       '(non-null :unit))
                             (assoc-in [:objects :speeder]
                                       {:implements [:vehicle]
                                        :fields {:id {:type '(non-null String)}
                                                 :name {:type '(non-null String)}
                                                 :length {:type 'Float
                                                          ;; invalid type of :unit arg (it's nullable)
                                                          :args {:unit {:type :unit}}}
                                                 :class {:type 'String}}}))]
      (expect-exception
        "Object field's argument is not compatible with extended interface's argument type."
        {:argument-name :speeder/length.unit
         :interface-name :vehicle}
        (schema/compile invalid-schema {:default-field-resolver schema/hyphenating-default-field-resolver}))))

  (testing "object includes additional (optional) field arguments that are not defined in the interface field"
    (let [schema (-> test-schema
                     (update-in [:objects :starship :fields :length :args]
                                #(assoc % :precision {:type 'Int})))]
      (is (map? (schema/compile schema {:default-field-resolver schema/hyphenating-default-field-resolver}))
          "should compile schema without any errors")))

  (testing "object includes additional (required) field argument that is not defined in the interface field"
    (let [schema (-> test-schema
                     (update-in [:objects :starship :fields :length :args]
                                #(assoc % :precision {:type '(non-null Int)})))]
      (expect-exception
        "Additional arguments on an object field that are not defined in extended interface cannot be required."
        {:argument-name :starship/length.precision
         :interface-name :vehicle}
        (schema/compile schema {:default-field-resolver schema/hyphenating-default-field-resolver})))))
