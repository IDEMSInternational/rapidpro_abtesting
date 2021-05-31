group_switch_node_template = '''
        {
          "uuid": "Node_UUID",
          "actions": [],
          "router": {
            "type": "switch",
            "cases": [
              {
                "uuid": "CaseA_UUID",
                "type": "has_group",
                "arguments": [
                  "GroupA_UUID",
                  "GroupA_name"
                ],
                "category_uuid": "GroupA_Category_UUID"
              },
              {
                "uuid": "CaseB_UUID",
                "type": "has_group",
                "arguments": [
                  "GroupB_UUID",
                  "GroupB_name"
                ],
                "category_uuid": "GroupB_Category_UUID"
              }
            ],
            "categories": [
              {
                "uuid": "GroupA_Category_UUID",
                "name": "GroupA_name",
                "exit_uuid": "ExitA_UUID"
              },
              {
                "uuid": "GroupB_Category_UUID",
                "name": "GroupB_name",
                "exit_uuid": "ExitB_UUID"
              },
              {
                "uuid": "Other_Category_UUID",
                "name": "Other",
                "exit_uuid": "ExitOther_UUID"
              }
            ],
            "default_category_uuid": "Other_Category_UUID",
            "operand": "@contact.groups",
            "result_name": ""
          },
          "exits": [
            {
              "uuid": "ExitA_UUID",
              "destination_uuid": "DestinationA_UUID"
            },
            {
              "uuid": "ExitB_UUID",
              "destination_uuid": "DestinationB_UUID"
            },
            {
              "uuid": "ExitOther_UUID",
              "destination_uuid": "DestinationB_UUID"
            }
          ]
        }
        '''

assign_to_group_template = '''
    {
      "nodes": [
        {
          "uuid": "EntryNode_UUID",
          "actions": [],
          "router": {
            "type": "switch",
            "cases": [
              {
                "uuid": "OneTimeUse_UUID",
                "type": "has_group",
                "arguments": [
                  "GroupA_UUID",
                  "GroupA_name"
                ],
                "category_uuid": "GroupA_Category_UUID"
              },
              {
                "uuid": "OneTimeUse_UUID",
                "type": "has_group",
                "arguments": [
                  "GroupB_UUID",
                  "GroupB_name"
                ],
                "category_uuid": "GroupB_Category_UUID"
              }
            ],
            "categories": [
              {
                "uuid": "GroupA_Category_UUID",
                "name": "GroupA_name",
                "exit_uuid": "ExitA_UUID"
              },
              {
                "uuid": "GroupB_Category_UUID",
                "name": "GroupB_name",
                "exit_uuid": "ExitB_UUID"
              },
              {
                "uuid": "Other_Category_UUID",
                "name": "Other",
                "exit_uuid": "ExitOther_UUID"
              }
            ],
            "default_category_uuid": "Other_Category_UUID",
            "operand": "@contact.groups",
            "result_name": ""
          },
          "exits": [
            {
              "uuid": "ExitA_UUID",
              "destination_uuid": "Destination_UUID"
            },
            {
              "uuid": "ExitB_UUID",
              "destination_uuid": "Destination_UUID"
            },
            {
              "uuid": "ExitOther_UUID",
              "destination_uuid": "PickRandomGroupNode_UUID"
            }
          ]
        },
        {
          "uuid": "PickRandomGroupNode_UUID",
          "actions": [],
          "router": {
            "type": "random",
            "categories": [
              {
                "uuid": "OneTimeUse_UUID",
                "name": "GroupA_name",
                "exit_uuid": "RandomChoiceGroupA_Exit"
              },
              {
                "uuid": "OneTimeUse_UUID",
                "name": "GroupB_name",
                "exit_uuid": "RandomChoiceGroupB_Exit"
              }
            ]
          },
          "exits": [
            {
              "uuid": "RandomChoiceGroupA_Exit",
              "destination_uuid": "AssignToGroupANode_UUID"
            },
            {
              "uuid": "RandomChoiceGroupB_Exit",
              "destination_uuid": "AssignToGroupBNode_UUID"
            }
          ]
        },
        {
          "uuid": "AssignToGroupANode_UUID",
          "actions": [
            {
              "type": "add_contact_groups",
              "groups": [
                {
                  "uuid": "GroupA_UUID",
                  "name": "GroupA_name"
                }
              ],
              "uuid": "OneTimeUse_UUID"
            }
          ],
          "exits": [
            {
              "uuid": "OneTimeUse_UUID",
              "destination_uuid": "Destination_UUID"
            }
          ]
        },
        {
          "uuid": "AssignToGroupBNode_UUID",
          "actions": [
            {
              "type": "add_contact_groups",
              "groups": [
                {
                  "uuid": "GroupB_UUID",
                  "name": "GroupB_name"
                }
              ],
              "uuid": "OneTimeUse_UUID"
            }
          ],
          "exits": [
            {
              "uuid": "OneTimeUse_UUID",
              "destination_uuid": "Destination_UUID"
            }
          ]
        }
      ],
      "_ui": {
        "nodes": {
          "EntryNode_UUID": {
            "type": "split_by_groups",
            "position": {
              "left": 200,
              "top": 40
            },
            "config": {
              "cases": {}
            }
          },
          "PickRandomGroupNode_UUID": {
            "type": "split_by_random",
            "position": {
              "left": 260,
              "top": 140
            },
            "config": null
          },
          "AssignToGroupANode_UUID": {
            "position": {
              "left": 160,
              "top": 260
            },
            "type": "execute_actions"
          },
          "AssignToGroupBNode_UUID": {
            "position": {
              "left": 380,
              "top": 260
            },
            "type": "execute_actions"
          }
        }
      }
    }  
    '''